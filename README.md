# AI-Powered Quiz Web App

This project is a production-ready Streamlit quiz app that:

- parses a syllabus PDF and detects chapters
- extracts PYQ text to mimic exam style
- retrieves only the relevant syllabus chunks for selected chapters
- generates MCQs with Groq using a RAG-style workflow
- runs an interactive quiz with progress tracking, timer support, retry mode, and detailed feedback

## Project Structure

```text
app.py
utils/pdf_parser.py
utils/chunking.py
utils/retriever.py
utils/mcq_generator.py
utils/evaluator.py
utils/cache.py
requirements.txt
README.md
```

## Features

- Streamlit-based UI for upload, quiz, and result flow
- Default PDF support using `Syllabus.pdf` and `SamplePYQs.pdf`
- Automatic chapter detection with manual section fallback
- Chunking into 300-500 word retrieval units
- Chapter-aware retrieval to limit token usage
- Groq-based MCQ generation with strict JSON validation
- JSON + in-memory cache to reduce repeated API calls
- Retry incorrect questions
- Score, percentage, explanations, and answer review



## Notes

- If a PDF is scanned and contains no extractable text, the app will ask for a text-based PDF.
- The app does not send the full syllabus to the model. It sends only retrieved chapter chunks.
- Generated MCQs are cached using chapter selection, difficulty, question count, and content fingerprints.
