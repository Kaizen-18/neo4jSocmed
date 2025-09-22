# app/neo4j_driver.py
from neo4j import AsyncGraphDatabase
import os
from dotenv import load_dotenv

load_dotenv()

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "test")

class Neo4jDriver:
    def __init__(self):
        self.driver = None

    def init_app(self):
        if self.driver is None:
            self.driver = AsyncGraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    async def close(self):
        if self.driver:
            await self.driver.close()
            self.driver = None

    async def execute_read(self, cypher: str, params: dict = None):
        params = params or {}
        async with self.driver.session() as session:
            result = await session.run(cypher, params)
            records = []
            async for rec in result:
                records.append(rec.data())
            return records

    async def execute_write(self, cypher: str, params: dict = None):
        params = params or {}
        async with self.driver.session() as session:
            result = await session.run(cypher, params)
            # return records if any
            records = []
            async for rec in result:
                records.append(rec.data())
            return records

neo4j_driver = Neo4jDriver()
