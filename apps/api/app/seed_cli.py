from app.db import Base, SessionLocal, engine
from app.seed import reset_and_seed

if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        reset_and_seed(db)
        print("Synthetic VoxRelay workspace seeded.")
    finally:
        db.close()
