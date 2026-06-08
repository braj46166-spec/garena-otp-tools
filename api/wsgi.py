from app import app as application

# Expose WSGI callable for Vercel
app = application

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
