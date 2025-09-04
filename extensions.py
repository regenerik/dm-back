from flask_executor import Executor

executor = None

def init_extensions(app):
    global executor
    executor = Executor(app)
