from main import app

if __name__ == "__main__":
    app.run()
```

3. **Vérifie que ton `Procfile` dit** :
```
web: gunicorn --bind 0.0.0.0:$PORT --workers 1 --timeout 120 wsgi:app
