import sys
import os

# Add current directory to path
sys.path.append(os.getcwd())

try:
    print("Attempting to import ChatRequest from app.schemas.chat_schema...")
    from app.schemas.chat_schema import ChatRequest
    print(f"Successfully imported ChatRequest: {ChatRequest}")
    print(f"ChatRequest bases: {ChatRequest.__bases__}")

    print("Attempting to import chat_router...")
    from app.routers import chat_router
    print("Successfully imported chat_router")
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
