from app import app

if __name__ == "__main__":
    app.run()
```

2. **Mets à jour ton `Procfile`** :
```
release: python -c "print('Ready')"
web: python app.py
