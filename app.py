import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta, date
import icalendar
from collections import defaultdict
import re
import io

st.set_page_config(
    page_title="Trip Visualizer",
    page_icon="🗺️",
    layout="wide"
)

# Custom CSS
st.markdown("""
<style>
    .metric-card {
        background-color: #f0f2f6;
        padding: 20px;
        border-radius: 10px;
        text-align: center;
    }
    .metric-value {
        font-size: 2.5em;
        font-weight: bold;
        margin: 10px 0;
    }
</style>
""", unsafe_allow_html=True)

@st.cache_data
def process_ics_file(uploaded_file):
    """Process ICS file and extract trip-related events"""
    try:
        # Read the ICS file
        ics_content = uploaded_file.read()
        cal = icalendar.Calendar.from_ical(ics_content)
        
        # More comprehensive travel keywords
        travel_keywords = [
            'flight', 'flights', 'fly', 'flying', 'airport', 'airline',
            'hotel', 'hotels', 'accommodation', 'motel', 'resort', 'hostel',
            'airbnb', 'booking.com', 'lodging',
            'trip', 'travel', 'traveling', 'travelling', 'journey',
            'vacation', 'vacations', 'holiday', 'holidays', 'getaway',
            'visit', 'visiting', 'tour', 'tourist', 'tourism',
            'cruise', 'cruising', 'sailing',
            'train', 'rail', 'railway', 'amtrak', 'eurostar',
            'bus', 'coach', 'greyhound',
            'rental car', 'rent a car', 'car rental', 'hire car',
            'check-in', 'checkin', 'check in',
            'check-out', 'checkout', 'check out',
            'reservation', 'reservations', 'booked', 'booking',
            'departure', 'departing', 'arrival', 'arriving',
            'itinerary', 'boarding pass', 'boarding',
            'terminal', 'gate', 'baggage', 'luggage',
            '✈️', '🏨', '🚂', '🚗', '🏖️', '🗺️', '🧳', '🎫', '🏝️', '⛱️'
        ]
        
        # Exclusion keywords - events that might have travel words but aren't trips
        exclusion_keywords = [
            'meeting', 'call', 'zoom', 'teams', 'virtual',
            'webinar', 'conference call', 'standup', 'stand-up',
            'interview', 'dental', 'doctor', 'appointment',
            'birthday', 'anniversary', 'party'
        ]
        
        trips = []
        
        for component in cal.walk():
            if component.name == "VEVENT":
                try:
                    summary = str(component.get('summary', ''))
                    location = str(component.get('location', ''))
                    description = str(component.get('description', ''))
                    
                    # Combine all text for searching
                    combined_text = (summary + " " + location + " " + description).lower()
                    
                    # Check exclusions first
                    if any(excl in combined_text for excl in exclusion_keywords):
                        continue
                    
                    # Count how many travel keywords match
                    travel_score = sum(1 for keyword in travel_keywords if keyword in combined_text)
                    
                    # Only consider it a trip if it has at least 2 travel keywords or strong indicators
                    strong_indicators = ['flight', 'hotel', 'airbnb', '✈️', '🏨', 'airport', 'check-in', 'check-out']
                    has_strong_indicator = any(indicator in combined_text for indicator in strong_indicators)
                    
                    if travel_score >= 2 or has_strong_indicator:
                        # Parse dates
                        start = component.get('dtstart')
                        end = component.get('dtend')
                        
                        if start is None:
                            continue
                        
                        # Handle different date formats
                        start_date = None
                        end_date = None
                        
                        if hasattr(start, 'dt'):
                            if isinstance(start.dt, datetime):
                                start_date = start.dt
                            elif isinstance(start.dt, date):
                                start_date = datetime.combine(start.dt, datetime.min.time())
                        
                        if end and hasattr(end, 'dt'):
                            if isinstance(end.dt, datetime):
                                end_date = end.dt
                            elif isinstance(end.dt, date):
                                end_date = datetime.combine(end.dt, datetime.min.time())
                        
                        # If we couldn't parse dates, skip this event
                        if start_date is None:
                            continue
                        
                        # If no end date, use start date
                        if end_date is None:
                            end_date = start_date
                        
                        trip_data = {
                            'title': summary,
                            'start_date': start_date,
                            'end_date': end_date,
                            'location': location,
                            'description': description[:200] if description else '',  # Limit description length
                            'destination': extract_destination(summary, location),
                            'travel_score': travel_score
                        }
                        trips.append(trip_data)
                
                except Exception as e:
                    # Skip events that cause errors
                    continue
        
        # Create DataFrame
        if trips:
            df = pd.DataFrame(trips)
            # Calculate duration
            df['duration_days'] = ((df['end_date'] - df['start_date']).dt.total_seconds() / 86400).round().astype(int) + 1
            # Sort by start date
            df = df.sort_values('start_date', ascending=False)
            # Remove duplicates based on title and start date
            df = df.drop_duplicates(subset=['title', 'start_date'])
            return df
        else:
            return pd.DataFrame()
    
    except Exception as e:
        st.error(f"Error processing file: {str(e)}")
        return pd.DataFrame()

def extract_destination(title, location):
    """Try to extract destination from title and location"""
    # Clean the inputs
    title = str(title).strip()
    location = str(location).strip()
    
    # Priority 1: Check location field
    if location and location.lower() not in ['', 'none', 'null']:
        # Common location patterns
        location_parts = location.split(',')
        if location_parts:
            # Get the city name (usually first part)
            city = location_parts[0].strip()
            # Remove common words
            city = re.sub(r'\b(airport|hotel|center|centre|downtown)\b', '', city, flags=re.IGNORECASE).strip()
            if city and len(city) > 2:
                return city.title()
    
    # Priority 2: Look for destinations in title
    # Pattern: "Flight to [Destination]" or "Trip to [Destination]"
    patterns = [
        r'(?:to|in|at)\s+([A-Z][a-zA-Z\s]+?)(?:\s*[-,:]|\s+on\s+|\s+from\s+|$)',
        r'([A-Z][a-zA-Z\s]+?)\s+(?:trip|vacation|holiday|flight|hotel)',
        r'^\s*([A-Z][a-zA-Z\s]+?)\s*[-:]',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, title)
        if match:
            destination = match.group(1).strip()
            # Remove common words that aren't destinations
            if destination.lower() not in ['the', 'hotel', 'flight', 'trip', 'vacation']:
                return destination
    
    # Priority 3: Extract proper nouns from title
    words = title.split()
    proper_nouns = []
    for i, word in enumerate(words):
        if word and word[0].isupper() and len(word) > 2:
            # Skip common travel words
            if word.lower() not in ['flight', 'hotel', 'trip', 'vacation', 'holiday', 'the', 'rental', 'car']:
                proper_nouns.append(word)
    
    if proper_nouns:
        # Return the first proper noun that looks like a place
        return proper_nouns[0]
    
    return "Unknown"

def create_timeline_chart(df):
    """Create a timeline visualization of trips"""
    if df.empty:
        fig = go.Figure()
        fig.add_annotation(text="No trip data available", x=0.5, y=0.5, showarrow=False)
        return fig
    
    # Sort by start date descending (most recent first)
    df_sorted = df.sort_values('start_date', ascending=False).
