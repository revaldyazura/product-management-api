# This is a sample Python script.

# Press Ctrl+F5 to execute it or replace it with your code.
# Press Double Shift to search everywhere for classes, files, tool windows, actions, and settings.


# def print_hi(name):
#     # Use a breakpoint in the code line below to debug your script.
#     print(f'Hi, {name}')  # Press F9 to toggle the breakpoint.
#
#
# # Press the green button in the gutter to run the script.
# if __name__ == '__main__':
#     print_hi('PyCharm')


# See PyCharm help at https://www.jetbrains.com/help/pycharm/
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os
import logging
from middleware.request_logger import RequestLoggingMiddleware
from utils.logging_config import setup_logging


CONTROLLER_MODULES = {
    "product": "product_controller",
    "user": "user_controller"
}
setup_logging()
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Product Management API", description="The API for product management"
)

os.makedirs(os.path.join("static", "avatars"), exist_ok=True)
os.makedirs(os.path.join("static", "products"), exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

# CORS configuration to allow frontend (React dev server) to call the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        'http://localhost:3000',
        'http://127.0.0.1:3000',
    ],
    allow_credentials=True,  # allow cookies/authorization headers if needed
    allow_methods=['*'],
    allow_headers=['*'],
)

app.add_middleware(RequestLoggingMiddleware)

for controller_name, module_name in CONTROLLER_MODULES.items():
        module = __import__(f"router.controller.{module_name}", fromlist=["router"])
        app.include_router(module.router)



@app.get("/")
def root():
    logger.info("Root endpoint accessed")
    return {"message": "Heal the World"}

