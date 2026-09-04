WHITE & BLACK - Render deployment

1. Push this whole folder to GitHub.
2. On Render, create a new Web Service from the GitHub repository.
3. Build Command: pip install -r requirements.txt
4. Start Command: gunicorn backend.app:app --bind 0.0.0.0:$PORT
5. Deploy.

Important:
- This project currently uses SQLite (backend/users.db) and local product image files.
- On Render Free, local filesystem data is not durable across restarts/redeploys.
- For a real public store with persistent users/orders/uploads, move the database to PostgreSQL and images to persistent object storage.
- The uploaded ZIP did not contain the original product image files. Put them in products/images/ before deployment if you want the listed product photos to appear.
- The uploaded ZIP also did not contain product-details.html or admin-login.html; deployment package includes basic versions of both.
