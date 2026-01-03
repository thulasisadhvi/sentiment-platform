# System Architecture

## 1. System Diagram

**Flow:**
`Ingester` -> `Worker (AI Model)` -> `Database` <- `Backend API` <-> `Frontend (Dashboard)`

## 2. Component Descriptions
* **Frontend (React):** A reactive SPA that visualizes live data using Recharts and manages WebSocket connections.
* **Backend (FastAPI):** High-performance async API that serves historical data and broadcasts real-time events.
* **Ingester:** Simulates a live stream of social media posts.
* **Worker:** Dedicated service for running heavy AI inference tasks using PyTorch/Transformers.
* **Database (PostgreSQL):** Persistent storage for all posts and sentiment results.

## 3. Data Flow
1.  **Ingestion:** Ingester generates raw text data.
2.  **Processing:** Worker analyzes text using the RoBERTa model.
3.  **Storage:** Result (Positive/Negative/Neutral) is saved to PostgreSQL.
4.  **Serving:** Backend detects new data and pushes it to Frontend via WebSockets.

## 4. Technology Justification
* **FastAPI:** Chosen for native async support, crucial for handling AI tasks and WebSockets concurrently.
* **RoBERTa:** Selected specifically for its ability to understand social media context and native "Neutral" sentiment, outperforming generic models like SST-2.
* **Docker:** Ensures consistent deployment across environments.

## 5. Database Schema
**Table: `posts`**
* `id` (PK): Integer
* `content`: Text
* `sentiment`: String (positive, negative, neutral)
* `confidence`: Float
* `created_at`: DateTime

## 6. API Design
* RESTful endpoints for historical data (`GET /posts`).
* WebSocket (`/ws`) for real-time data streaming.
* Standard JSON response formats.

## 7. Scalability Considerations
The architecture allows for horizontal scaling. The **Worker** service is stateless and can be replicated to handle higher data ingestion rates without modifying the backend or frontend.

## 8. Security Considerations
* Environment variable management for all secrets.
* CORS restrictions on API endpoints.
