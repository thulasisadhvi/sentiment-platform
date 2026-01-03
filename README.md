
#  Real-Time AI Sentiment Analysis Platform

A scalable, containerized full-stack application that ingests social media data, performs real-time sentiment analysis using advanced Transformer models (RoBERTa), and visualizes insights via an interactive dashboard.

## 1. Project Title and Description
**Real-Time AI Sentiment Analysis Platform** This project is a full-stack solution designed to simulate, analyze, and visualize social media sentiment in real-time. It leverages a microservices architecture to ingest text streams, processes them using the `twitter-roberta-base-sentiment` AI model for high-accuracy classification (Positive, Negative, Neutral), and displays live trends on a reactive dashboard.

## 2. Features List
* **Real-Time Ingestion:** Simulates high-volume social media data streams.
* **Advanced AI Analysis:** Uses `cardiffnlp/twitter-roberta-base-sentiment-latest` for context-aware sentiment detection.
* **Native Neutrality:** Accurately identifies neutral statements without arbitrary thresholds.
* **Live Dashboard:** Interactive React frontend displaying real-time trends via WebSockets.
* **Scalable Architecture:** Fully containerized microservices orchestrated with Docker Compose.
* **Robust Testing:** Comprehensive test suite with >75% code coverage.

## 3. Architecture Overview
The system is built as a set of containerized microservices (Ingester, Worker, Backend, Frontend, Database) that work together to process data asynchronously. For a detailed breakdown of the system design, data flow, and technology choices, please refer to [ARCHITECTURE.md](ARCHITECTURE.md).

## 4. Prerequisites
* **Docker** (v20.10+) and **Docker Compose** (v2.0+)
* **RAM:** 4GB minimum (8GB recommended for AI models)
* **Ports:** Ensure ports `3000` (Frontend) and `8000` (Backend) are available.
* **API Keys:** Hugging Face Token (recommended) and Groq API Key (optional).

## 5. Quick Start

```bash
# Clone repository
git clone https://github.com/thulasisadhvi/sentiment-platform
cd sentiment-platform

# Copy environment template
cp .env.example .env

# Edit .env file with your API keys
nano .env

# Start all services
docker-compose up -d --build

# Wait for services to be healthy (30-60 seconds)
docker-compose ps

# Access dashboard
# Open http://localhost:3000 in browser

# Stop services
docker-compose down

```

## 6. Configuration

The application is configured via the `.env` file. Key variables include:

* `HUGGINGFACE_MODEL`: The AI model used (default: `cardiffnlp/twitter-roberta-base-sentiment-latest`).
* `HF_TOKEN`: Your Hugging Face API token .
* `DATABASE_URL`: PostgreSQL connection string (default: `postgresql+asyncpg://user:password@db/sentiment_db`).
* `GROQ_API_KEY`:  API key for external LLM integration.

## 7. API Documentation

The backend provides a RESTful API and WebSocket endpoints. Interactive documentation is available at:

* **Swagger UI:** `http://localhost:8000/docs`
* **ReDoc:** `http://localhost:8000/redoc`

**Key Endpoints:**

* `GET /health`: Check system status.
* `GET /sentiment/stats`: Retrieve aggregated sentiment statistics.
* `WS /ws/sentiment`: WebSocket endpoint for real-time updates.

## 8. Testing Instructions

The project includes a comprehensive test suite using `pytest`. To run tests inside the container:

```bash
docker-compose exec backend pytest --cov=backend --cov-report=term

```

*Current Code Coverage: >75%*

## 9. Troubleshooting

* **Container exited with code 137:** This indicates an Out of Memory error. Increase Docker's memory allocation to at least 4GB.
* **Connection Refused (localhost:3000):** The frontend build might still be in progress. Check logs with `docker-compose logs -f frontend`.
* **Pytest "not found":** Ensure dependencies are installed by running `docker-compose up -d --build`.

## 10. Project Structure

```bash
sentiment-platform/
├── backend/             # FastAPI Application & AI Logic
├── frontend/            # React Dashboard
├── docker-compose.yml   # Container Orchestration
├── .env.example         # Environment Configuration
├── ARCHITECTURE.md      # Detailed System Design
└── README.md            # Project Documentation

```

## 11. License

This project is licensed under the MIT License.
