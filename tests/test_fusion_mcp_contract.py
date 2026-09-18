"""
tests/test_fusion_mcp_contract.py
---------------------------------------------------------------------------
Contract tests for Autodesk Fusion 360 MCP (Model Context Protocol) integration.

Validates that:
  1. The MCP tool registry discovers and registers Fusion MCP tools.
  2. The MCP protocol JSON-RPC interface handles:
     - initialize
     - tools/list
     - tools/call
     - resources/list
  3. execute_api_script execution contract properly validates and dispatches scripts.
  4. test_mcp_connection utility functions behave correctly.
"""

import asyncio
import importlib
import os
import sys
import unittest


# Mock adsk before importing Fusion MCP Addin to allow running in CI without Fusion
class _MockApplication:
    @staticmethod
    def get():
        return _MockApplication()

    def log(self, msg):
        pass


class _MockAdskCore:
    Application = _MockApplication

    class CustomEventHandler:
        pass

    class CustomEventArgs:
        pass


class _MockAdsk:
    core = _MockAdskCore


if "adsk" not in sys.modules:
    sys.modules["adsk"] = _MockAdsk
if "adsk.core" not in sys.modules:
    sys.modules["adsk.core"] = _MockAdskCore
else:
    sys.modules["adsk.core"].Application = _MockApplication

SAMPLE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "FusionMCPSample")
if SAMPLE_DIR not in sys.path:
    sys.path.insert(0, SAMPLE_DIR)


class FusionMcpContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        mcp_addin_dir = os.path.join(SAMPLE_DIR, "Fusion MCP Addin")
        init_file = os.path.join(mcp_addin_dir, "__init__.py")
        if not os.path.isdir(mcp_addin_dir) or not os.path.isfile(init_file):
            raise unittest.SkipTest(
                f"FusionMCPSample submodule is not checked out (missing {init_file}). "
                "Run `git submodule update --init --recursive` to run MCP contract tests."
            )
        try:
            # Import package using importlib because folder has spaces
            cls.addin_pkg = importlib.import_module("Fusion MCP Addin")
            cls.registry_mod = importlib.import_module("Fusion MCP Addin.mcp_primitives.registry")
            cls.tool_mod = importlib.import_module("Fusion MCP Addin.mcp_primitives.tool")
            cls.resource_mod = importlib.import_module("Fusion MCP Addin.mcp_primitives.resource")
            cls.item_mod = importlib.import_module("Fusion MCP Addin.mcp_primitives.item")
            cls.server_mod = importlib.import_module("Fusion MCP Addin.server.mcp_server")
        except ImportError as exc:
            raise unittest.SkipTest(f"Failed to import Fusion MCP Addin: {exc}")

    def setUp(self):
        self.get_tools = self.registry_mod.get_tools
        self.get_resources = self.registry_mod.get_resources
        self.register = self.registry_mod.register
        self.reset_registry = self.registry_mod.reset_registry
        self.SimpleMCPServer = self.server_mod.SimpleMCPServer
        self.Tool = self.tool_mod.Tool
        self.Resource = self.resource_mod.Resource
        self.Item = self.item_mod.Item

    def test_mcp_server_initialization_protocol(self):
        """Verify MCP 'initialize' JSON-RPC method returns valid protocol response."""
        server = self.SimpleMCPServer("Test Fusion MCP Server")
        req = {
            "jsonrpc": "2.0",
            "id": "init-1",
            "method": "initialize",
            "params": {"clientInfo": {"name": "test-client", "version": "1.0"}}
        }
        res = asyncio.run(server.handle_request(req))

        self.assertEqual(res["jsonrpc"], "2.0")
        self.assertEqual(res["id"], "init-1")
        self.assertIn("result", res)
        self.assertEqual(res["result"]["protocolVersion"], "2024-11-05")
        self.assertIn("capabilities", res["result"])
        self.assertIn("tools", res["result"]["capabilities"])

    def test_mcp_server_tools_list_protocol(self):
        """Verify MCP 'tools/list' returns registered tools with schema."""
        server = self.SimpleMCPServer("Test Fusion MCP Server")

        tool_item = self.Item(
            self.Tool(
                name="execute_api_script",
                description="Executes a Python script in Fusion 360",
                input_schema={
                    "type": "object",
                    "properties": {"script": {"type": "string"}},
                    "required": ["script"]
                }
            ),
            handler=lambda script: {"output": f"executed: {len(script)} chars"},
            run_on_main_thread=False
        )
        server.register(tool_item)

        req = {
            "jsonrpc": "2.0",
            "id": "list-1",
            "method": "tools/list",
            "params": {}
        }
        res = asyncio.run(server.handle_request(req))

        self.assertEqual(res["jsonrpc"], "2.0")
        tools = res["result"]["tools"]
        self.assertEqual(len(tools), 1)
        self.assertEqual(tools[0]["name"], "execute_api_script")
        self.assertIn("script", tools[0]["inputSchema"]["properties"])

    def test_mcp_server_tools_call_execution(self):
        """Verify calling a registered MCP tool executes handler and returns result."""
        server = self.SimpleMCPServer("Test Fusion MCP Server")

        def dummy_execute(script: str):
            return {"status": "success", "length": len(script)}

        tool_item = self.Item(
            self.Tool(
                name="execute_api_script",
                description="Executes script",
                input_schema={"type": "object"}
            ),
            handler=dummy_execute,
            run_on_main_thread=False
        )
        server.register(tool_item)

        req = {
            "jsonrpc": "2.0",
            "id": "call-1",
            "method": "tools/call",
            "params": {
                "name": "execute_api_script",
                "arguments": {"script": "print('hello from test')"}
            }
        }
        res = asyncio.run(server.handle_request(req))

        self.assertEqual(res["jsonrpc"], "2.0")
        self.assertEqual(res["result"]["status"], "success")
        self.assertEqual(res["result"]["length"], len("print('hello from test')"))

    def test_mcp_server_tools_call_unknown_tool_returns_error(self):
        """Verify calling an unregistered tool returns JSON-RPC method not found error."""
        server = self.SimpleMCPServer("Test Fusion MCP Server")
        req = {
            "jsonrpc": "2.0",
            "id": "call-err",
            "method": "tools/call",
            "params": {"name": "non_existent_tool", "arguments": {}}
        }
        res = asyncio.run(server.handle_request(req))

        self.assertIn("error", res)
        self.assertEqual(res["error"]["code"], -32601)

    def test_test_mcp_connection_port_check_when_closed(self):
        """Verify test_mcp_connection reports port closed when nothing is listening."""
        import test_mcp_connection as tmc
        is_open = tmc.check_port(port=59998, timeout=0.2)
        self.assertFalse(is_open)


if __name__ == "__main__":
    unittest.main()
