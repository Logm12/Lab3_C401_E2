import json
import os
import time
from datetime import datetime, date as date_type
from typing import Any, Dict, List, Optional

import requests


USER_AGENT = "travelbot-lab/1.0"


def _get_tavily_api_key() -> Optional[str]:
    return os.getenv("TAVILY_API_KEY") or os.getenv("TAVI_API_KEY")