from fastapi import FastAPI, HTTPException, status
import uvicorn
from typing import Any
from pydantic import BaseModel
import json
app = FastAPI()
filename = "students.json"
with open("students.json", "r") as file:
    students = json.load(file)


class studentmodel(BaseModel):
    name: str
    age: int
    major: str


@app.get('/')
def root():
    return {"Home": " Our home endpoint"}


@app.get('/studentdata/{id}')
def search_student(id: str):
    if id in students.keys():
        return students[id]

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND, detail=" No student with such id"
    )


@app.post('/studentdata')
def add_student(body: studentmodel):
    id = list(students.keys())
    id = int(id[len(id)-1])+1
    students[id] = {
        "id": id,
        **body.model_dump()
    }
    with open(filename, "w")as file:
        json.dump(students, file, indent=4)

    return students[id]


@app.delete('/studentdata/{id}')
def deletestudent(id: int):
    try:
        students.pop(str(id))
        with open(filename, "w")as file:
            json.dump(students, file, indent=4)
        return {"details:", f"student with id {id} has been deleted"}
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=" given id not found"
        )

    # if __name__ == "__main__":
    #     uvicorn.run("main:app",host="127.0.0.1",port=800,reload=True)
