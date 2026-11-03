import os
import inngest
from dotenv import load_dotenv

load_dotenv()

# Initialize Inngest client
# app_id is required. signing_key and event_key are usually picked up from environment variables
# INNGEST_SIGNING_KEY and INNGEST_EVENT_KEY
inngest_client = inngest.Inngest(
    app_id="stockpulse-pro"
)
