pip install -r requirements.txt
export GEMINI_API_KEY=ddd...

# With a file
python main.py --email sample_email.txt

# Pipe stdin
echo "Can we reschedule tomorrow's meeting?" | python main.py --stdin

# JSON output (for platform ingestion)
python main.py --email sample_email.txt --json

# Health check
python main.py --health