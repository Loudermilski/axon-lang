"""
AXON Mock Runtime
Simple local environment for executing generated AXON code.
"""

class MockDB:
    def __init__(self):
        self.tables = {}

    def __getitem__(self, name):
        if name not in self.tables:
            self.tables[name] = Table()
        return self.tables[name]

class Table:
    def __init__(self):
        self.data = []

    async def find_one(self, q):
        for item in self.data:
            if all(item.get(k) == v for k, v in q.items()):
                return item
        return None

    async def create(self, d):
        self.data.append(d)
        return d

    async def update(self, q, d):
        item = await self.find_one(q)
        if item:
            item.update(d)
        return item

    async def delete(self, q):
        item = await self.find_one(q)
        if item:
            self.data.remove(item)

class MockMCP:
    def __getitem__(self, name):
        return Service()

class Service:
    def __getitem__(self, name):
        async def mock_tool(args):
            print(f"[MCP] Calling tool: {name} with {args}")
            return f"mock_result_for_{name}"
        return mock_tool

# Singleton instances for testing
db = MockDB()
mcp = MockMCP()
