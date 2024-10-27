from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError

try:
    engine = create_engine('postgresql://postgres:1234@localhost/bibiani_spatial_planning')
    connection = engine.connect()
    print("Successfully connected to the database!")
    connection.close()
except SQLAlchemyError as e:
    print("An error occurred while connecting to the database:")
    print(str(e))