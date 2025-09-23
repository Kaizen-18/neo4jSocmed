# app/main.py
import uvicorn
from fastapi import FastAPI, HTTPException, status, Depends
from uuid import uuid4
from datetime import datetime
import os
from dotenv import load_dotenv
from app.neo4j_driver import neo4j_driver
from app import schemas

load_dotenv()

app = FastAPI(title="FastAPI + Neo4j Social API")

@app.get("/")
async def root():
    return {"message": "Welcome to Neo4j Social Media API 🚀", "docs": "/docs"}


# startup/shutdown
@app.on_event("startup")
async def startup():
    neo4j_driver.init_app()
    # create common constraints (run once is fine)
    # unique username and unique post id
    await neo4j_driver.execute_write("CREATE CONSTRAINT IF NOT EXISTS FOR (u:User) REQUIRE u.username IS UNIQUE")
    await neo4j_driver.execute_write("CREATE CONSTRAINT IF NOT EXISTS FOR (p:Post) REQUIRE p.id IS UNIQUE")

@app.on_event("shutdown")
async def shutdown():
    await neo4j_driver.close()

# Helper to return single record or raise
def _single_or_none(records):
    if not records:
        return None
    # records are list of dicts from rec.data()
    # each dict will contain the named return keys from cypher
    return records[0]

# Users
@app.post("/users", response_model=schemas.UserOut, status_code=status.HTTP_201_CREATED)
async def create_user(payload: schemas.UserCreate):
    user_id = str(uuid4())
    created_at = datetime.utcnow().isoformat()
    cypher = """
    CREATE (u:User {
        id: $id, username: $username, name: $name, bio: $bio, created_at: $created_at
    })
    RETURN u.id AS id, u.username AS username, u.name AS name, u.bio AS bio
    """
    params = {
        "id": user_id,
        "username": payload.username,
        "name": payload.name,
        "bio": payload.bio,
        "created_at": created_at
    }
    try:
        records = await neo4j_driver.execute_write(cypher, params)
    except Exception as e:
        # likely uniqueness constraint violation
        raise HTTPException(status_code=400, detail=str(e))
    rec = _single_or_none(records)
    return rec

@app.get("/users/{username}", response_model=dict)
async def get_user(username: str):
    cypher = """
    MATCH (u:User {username: $username})
    OPTIONAL MATCH (u)-[:FOLLOWS]->(f:User)
    OPTIONAL MATCH (g:User)-[:FOLLOWS]->(u)
    OPTIONAL MATCH (u)-[:POSTED]->(p:Post)
    RETURN u.id AS id, u.username AS username, u.name AS name, u.bio AS bio,
           count(DISTINCT f) AS following_count, count(DISTINCT g) AS followers_count,
           count(DISTINCT p) AS posts_count
    """
    records = await neo4j_driver.execute_read(cypher, {"username": username})
    rec = _single_or_none(records)
    if not rec:
        raise HTTPException(status_code=404, detail="User not found")
    return rec

# Follow
@app.post("/follow", status_code=201)
async def follow(action: schemas.FollowAction):
    cypher = """
    MATCH (a:User {username: $a}), (b:User {username: $b})
    MERGE (a)-[r:FOLLOWS]->(b)
    RETURN a.username AS follower, b.username AS followee
    """
    params = {"a": action.follower_username, "b": action.followee_username}
    records = await neo4j_driver.execute_write(cypher, params)
    if not records:
        raise HTTPException(status_code=404, detail="One or both users not found")
    return {"detail": "OK", "data": records[0]}

# Unfollow
@app.post("/unfollow", status_code=200)
async def unfollow(action: schemas.FollowAction):
    cypher = """
    MATCH (a:User {username: $a})-[r:FOLLOWS]->(b:User {username: $b})
    DELETE r
    RETURN count(r) AS deleted
    """
    params = {"a": action.follower_username, "b": action.followee_username}
    await neo4j_driver.execute_write(cypher, params)
    return {"detail": "OK"}

# Posts
@app.post("/posts", response_model=schemas.PostOut, status_code=201)
async def create_post(payload: schemas.PostCreate):
    post_id = str(uuid4())
    created_at = datetime.utcnow().isoformat()
    cypher = """
    MATCH (a:User {username: $author_username})
    CREATE (p:Post {id: $id, content: $content, created_at: $created_at})
    CREATE (a)-[:POSTED]->(p)
    RETURN p.id AS id, a.username AS author_username, p.content AS content, p.created_at AS created_at
    """
    params = {
        "id": post_id,
        "content": payload.content,
        "author_username": payload.author_username,
        "created_at": created_at
    }
    records = await neo4j_driver.execute_write(cypher, params)
    rec = _single_or_none(records)
    if not rec:
        raise HTTPException(status_code=404, detail="Author not found")
    return rec

@app.get("/posts/{post_id}", response_model=dict)
async def get_post(post_id: str):
    cypher = """
    MATCH (p:Post {id: $id})<-[:POSTED]-(a:User)
    OPTIONAL MATCH (u:User)-[:LIKED]->(p)
    RETURN p.id AS id, a.username AS author_username, p.content AS content, p.created_at AS created_at, count(u) AS likes
    """
    records = await neo4j_driver.execute_read(cypher, {"id": post_id})
    rec = _single_or_none(records)
    if not rec:
        raise HTTPException(status_code=404, detail="Post not found")
    return rec

# Like post
@app.post("/posts/{post_id}/like")
async def like_post(post_id: str, payload: schemas.LikeAction):
    cypher = """
    MATCH (u:User {username: $username}), (p:Post {id: $post_id})
    MERGE (u)-[:LIKED]->(p)
    RETURN u.username AS username, p.id AS post_id
    """
    params = {"username": payload.username, "post_id": post_id}
    records = await neo4j_driver.execute_write(cypher, params)
    if not records:
        raise HTTPException(status_code=404, detail="User or post not found")
    return {"detail": "liked", "data": records[0]}

# Feed: posts from people the user follows (latest first)
@app.get("/feed/{username}", response_model=list)
async def get_feed(username: str, limit: int = 20):
    cypher = """
    MATCH (me:User {username: $username})-[:FOLLOWS]->(other:User)-[:POSTED]->(p:Post)
    RETURN p.id AS id, other.username AS author_username, p.content AS content, p.created_at AS created_at
    ORDER BY p.created_at DESC
    LIMIT $limit
    """
    records = await neo4j_driver.execute_read(cypher, {"username": username, "limit": limit})
    return records

if __name__ == "__main__":
    uvicorn.run("app.main:app", host=os.getenv("APP_HOST", "0.0.0.0"), port=int(os.getenv("APP_PORT", 8000)), reload=True)
