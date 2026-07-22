import json
import os
from datetime import datetime, timezone

import streamlit as st

st.title("Live match")
event_id = st.text_input("Event ID")
if event_id:
    try:
        from redis import Redis

        store = Redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379"))
        value = store.get(f"live:{event_id}")
        if value:
            prediction = json.loads(value)
            observed = datetime.fromisoformat(prediction["prediction_timestamp"])
            age = (datetime.now(timezone.utc) - observed).total_seconds()
            st.warning("Stale stream" if age > 60 else "Live")
            st.json(prediction)
        else:
            st.info("No live state for this event.")
    except Exception as exc:
        st.error(f"Live serving store unavailable: {exc}")
