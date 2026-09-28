import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError

from database import engine, SessionLocal, Base
from models import Laptop



LAPTOPS_INICIALES = [
    {"marca": "Dell", "modelo": "Latitude 5440", "ram_gb": 16, "disponible": True},
    {"marca": "Lenovo", "modelo": "ThinkPad E14", "ram_gb": 8, "disponible": False},
    {"marca": "HP", "modelo": "ProBook 450", "ram_gb": 16, "disponible": True},
]


def esperar_mysql(intentos: int = 10, espera: int = 3):
    """Reintenta la conexión mientras MySQL termina de arrancar."""
    for intento in range(1, intentos + 1):
        try:
            with engine.connect():
                return
        except OperationalError:
            print(f"MySQL no está listo (intento {intento}/{intentos}), reintentando...")
            time.sleep(espera)
    raise RuntimeError("No se pudo conectar a MySQL")


def cargar_datos_iniciales():
    db = SessionLocal()
    try:
        if db.query(Laptop).count() == 0:
            for datos in LAPTOPS_INICIALES:
                db.add(Laptop(**datos))
            db.commit()
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    esperar_mysql()
    Base.metadata.create_all(bind=engine)
    cargar_datos_iniciales()
    yield


app = FastAPI(lifespan=lifespan)



def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()



class LaptopCreate(BaseModel):
    marca: str
    modelo: str
    ram_gb: int


class LaptopResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    marca: str
    modelo: str
    ram_gb: int
    disponible: bool



@app.get("/")
def inicio():
    return {"mensaje": "API del laboratorio de cómputo"}


@app.get("/laptops", response_model=list[LaptopResponse])
def listar_laptops(db: Session = Depends(get_db)):
    return db.query(Laptop).order_by(Laptop.id).all()


@app.get("/laptops/disponibles", response_model=list[LaptopResponse])
def listar_disponibles(db: Session = Depends(get_db)):
    return (
        db.query(Laptop)
        .filter(Laptop.disponible == True)  
        .order_by(Laptop.id)
        .all()
    )


@app.get("/laptops/{laptop_id}", response_model=LaptopResponse)
def obtener_laptop(laptop_id: int, db: Session = Depends(get_db)):
    laptop = db.get(Laptop, laptop_id)
    if laptop is None:
        raise HTTPException(status_code=404, detail="Laptop no encontrada")
    return laptop


@app.post("/laptops", response_model=LaptopResponse, status_code=201)
def crear_laptop(laptop: LaptopCreate, db: Session = Depends(get_db)):
    nueva = Laptop(**laptop.model_dump(), disponible=True)
    db.add(nueva)
    db.commit()
    db.refresh(nueva)
    return nueva