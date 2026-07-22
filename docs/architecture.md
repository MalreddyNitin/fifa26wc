# Architecture

```mermaid
flowchart LR
  Sofa[SofaScore API] --> Bronze[Bronze raw JSON]
  Bronze --> Silver[Silver canonical Parquet]
  Silver --> Spark[Spark batch parity jobs]
  Silver --> WH[(PostgreSQL warehouse)]
  WH --> dbt[dbt marts and tests]
  Silver --> Gold[Gold feature marts]
  Gold --> Train[Model training + MLflow]
  Train --> Pred[Prediction artifacts]
  Pred --> API[FastAPI + gRPC]
  Pred --> Sim[50k tournament simulation]
  API --> UI[Streamlit dashboard]
  Sim --> UI
  Airflow[Airflow] -. orchestrates .-> Bronze
  Airflow -. orchestrates .-> Train
  Airflow -. orchestrates .-> Sim
```

Local development uses content-addressed files and PostgreSQL so the entire
batch platform is demonstrable without cloud credentials. MinIO mirrors the
S3-compatible lake contract. Spark implements the distributable reference
jobs; pandas remains the validated implementation at the current data scale.

## Service sequence

```mermaid
sequenceDiagram
  participant Client
  participant API
  participant Features
  participant Models
  Client->>API: Predict from SofaScore match URL
  API->>Sofa: Fetch public event metadata by event ID
  Sofa-->>API: Teams, kickoff, competition, round, venue
  API->>Features: pre-kickoff lagged team/opponent form and context
  Features-->>API: schema-validated feature row
  API->>Models: outcome + scoreline inference
  Models-->>API: calibrated probabilities and xG
  API-->>Client: versioned prediction
```
