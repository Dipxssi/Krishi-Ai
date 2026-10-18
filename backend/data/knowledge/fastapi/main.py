from fastapi import FastAPI
from fastapi.params import Body
from pydantic import BaseModel
from typing import Optional
app=FastAPI()
class Post(BaseModel):
    title:str
    content:str
    published:bool=True
    raiting:Optional[int]=None
@app.get("/")
async def root():
    return {"message":"hello mosa ji"}
@app.get("/post")
def get_post():
    return{"data":"here is your post"}
@app.post("/create_post")
def create_post(new_post:Post):
    print(new_post.published)
    return {"data":"new post"}
