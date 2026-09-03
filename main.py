"""Entrypoint: `uvicorn main:app` or `python main.py`."""
from app.api import create_app

app = create_app()

if __name__ == "__main__":
    import uvicorn
    from dotenv import load_dotenv

    load_dotenv()

    from app.config import get_settings

    settings = get_settings()
    uvicorn.run("main:app", host="0.0.0.0", port=settings.api_port, reload=True)
