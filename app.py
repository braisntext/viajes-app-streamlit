import pickle
import hashlib
from trip_map_optimized import render_trip_map_fast
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

@st.cache_data(ttl=3600)  # Cache for 1 hour
def get_file_hash(file_content):
    """Generate hash of file content"""
    return hashlib.md5(file_content).hexdigest()

@st.cache_data(persist="disk", ttl=86400)  # Cache for 24 hours
def process_ics_file(file_hash, file_content):
    """Process ICS file and extract trip-related events"""
    # Check if we have cached data
    if 'cached_trips' in st.session_state:
        cached_df = st.session_state['cached_trips']
        # Get the latest date from cached data
        if not cached_df.empty:
            last_date = cached_df['start_date'].max()
            st.info(f"Using cached data. Adding only new trips after {last_date.strftime('%Y-%m-%d')}")
    try:
        # Read the ICS file
        ics_content = file_content
        cal = icalendar.Calendar.from_ical(ics_content)
        
        # Travel keywords including booking platforms
        travel_keywords = [
            # Booking platforms (high priority)
            'airbnb', 'booking.com', 'agoda', 'trip.com', 'hotels.com',
            'expedia', 'kayak', 'priceline', 'tripadvisor', 'hostelworld',
            'vrbo', 'trivago', 'marriott', 'hilton', 'hyatt',
            
            # Transportation
            'flight', 'flights', 'fly', 'flying', 'airport', 'airline',
            'train', 'rail', 'railway', 'amtrak', 'eurostar',
            'bus', 'coach', 'greyhound', 'flixbus',
            'rental car', 'rent a car', 'car rental', 'hire car',
            'uber', 'lyft', 'taxi', 'transfer',
            
            # Accommodation
            'hotel', 'hotels', 'accommodation', 'motel', 'resort', 'hostel',
            'lodge', 'inn', 'suite', 'apartment', 'villa',
            
            # Trip related
            'trip', 'travel', 'traveling', 'travelling', 'journey',
            'vacation', 'vacations', 'holiday', 'holidays', 'getaway',
            'visit', 'visiting', 'tour', 'tourist', 'tourism',
            'cruise', 'cruising', 'sailing',
            
            # Check-in/out
            'check-in', 'checkin', 'check in',
            'check-out', 'checkout', 'check out',
            'reservation', 'reservations', 'booked', 'booking',
            
            # Travel emojis
            '✈️', '🏨', '🚂', '🚗', '🏖️', '🗺️', '🧳', '🎫', '🏝️', '⛱️'
        ]
        
        # Booking platforms for strong matching
        booking_platforms = [
            'airbnb', 'booking.com', 'agoda', 'trip.com', 'hotels.com',
            'expedia', 'kayak', 'priceline', 'tripadvisor', 'hostelworld',
            'vrbo', 'trivago'
        ]
        
        # Exclusion keywords
        exclusion_keywords = [
            'meeting', 'call', 'zoom', 'teams', 'virtual',
            'webinar', 'conference call', 'standup', 'stand-up',
            'interview', 'dental', 'doctor', 'appointment',
            'birthday', 'anniversary', 'party', 'work', 'office'
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
                    
                    # Check if it contains any booking platform - automatic include
                    has_booking_platform = any(platform in combined_text for platform in booking_platforms)
                    
                    # Count travel keywords
                    travel_score = sum(1 for keyword in travel_keywords if keyword in combined_text)
                    
                    # Include if: has booking platform OR has 2+ travel keywords
                    if has_booking_platform or travel_score >= 1:

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
                                # Remove timezone info to avoid comparison issues
                                if start_date.tzinfo is not None:
                                    start_date = start_date.replace(tzinfo=None)
                            elif isinstance(start.dt, date):
                                start_date = datetime.combine(start.dt, datetime.min.time())
                        
                        if end and hasattr(end, 'dt'):
                            if isinstance(end.dt, datetime):
                                end_date = end.dt
                                # Remove timezone info to avoid comparison issues
                                if end_date.tzinfo is not None:
                                    end_date = end_date.replace(tzinfo=None)
                            elif isinstance(end.dt, date):
                                end_date = datetime.combine(end.dt, datetime.min.time())
                        
                        if start_date is None:
                            continue
                        
                        if end_date is None:
                            end_date = start_date
                        
                        trip_data = {
                            'title': summary,
                            'start_date': start_date,
                            'end_date': end_date,
                            'location': location,
                            'description': description[:200] if description else '',
                            'destination': extract_destination(summary, location),
                            'travel_score': travel_score,
                            'has_booking_platform': has_booking_platform
                        }
                        trips.append(trip_data)
                
                except Exception as e:
                    continue
        
        # Create DataFrame
        if trips:
            df = pd.DataFrame(trips)
            # Calculate duration without using .dt accessor
            df['duration_days'] = df.apply(
                lambda row: ((row['end_date'] - row['start_date']).total_seconds() / 86400) + 1 
                if pd.notna(row['end_date']) and pd.notna(row['start_date']) 
                else 1, 
                axis=1
            ).round().astype(int)
            df = df.sort_values('start_date', ascending=False)
            df = df.drop_duplicates(subset=['title', 'start_date'])
            return df
        else:
            return pd.DataFrame()
    
    except Exception as e:
        st.error(f"Error processing file: {str(e)}")
        return pd.DataFrame()

def extract_destination(title, location):
    """Extract destination from title and location"""
    title = str(title).strip()
    location = str(location).strip()
    
    # Check location field first
    if location and location.lower() not in ['', 'none', 'null']:
        location_parts = location.split(',')
        if location_parts:
            city = location_parts[0].strip()
            city = re.sub(r'\b(airport|hotel|center|centre|downtown)\b', '', city, flags=re.IGNORECASE).strip()
            if city and len(city) > 2:
                return city.title()
    
    # Patterns for extracting destination from title
    patterns = [
        r'(?:to|in|at)\s+([A-Z][a-zA-Z\s]+?)(?:\s*[-,:]|\s+on\s+|\s+from\s+|$)',
        r'([A-Z][a-zA-Z\s]+?)\s+(?:trip|vacation|holiday|flight|hotel)',
        r'^\s*([A-Z][a-zA-Z\s]+?)\s*[-:]',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, title)
        if match:
            destination = match.group(1).strip()
            if destination.lower() not in ['the', 'hotel', 'flight', 'trip', 'vacation']:
                return destination
    
    # Extract proper nouns
    words = title.split()
    for word in words:
        if word and word[0].isupper() and len(word) > 2:
            if word.lower() not in ['flight', 'hotel', 'trip', 'vacation', 'holiday', 'the', 'rental', 'car']:
                return word
    
    return "Unknown"

def create_timeline_chart(df):
    """Create a timeline visualization of trips"""
    if df.empty:
        fig = go.Figure()
        fig.add_annotation(text="No trip data available", x=0.5, y=0.5, showarrow=False)
        return fig
    
    # Sort by start date descending
    df_sorted = df.sort_values('start_date', ascending=False).head(20)  # Show last 20 trips
    
    fig = go.Figure()
    
    # Create timeline bars
    for idx, row in df_sorted.iterrows():
        fig.add_trace(go.Scatter(
            x=[row['start_date'], row['end_date']],
            y=[row['destination'], row['destination']],
            mode='lines',
            line=dict(width=20, color='#3498db'),
            name=row['destination'],
            showlegend=False,
            hovertemplate=(
                f"<b>{row['title']}</b><br>" +
                f"Destination: {row['destination']}<br>" +
                f"Start: {row['start_date'].strftime('%Y-%m-%d')}<br>" +
                f"End: {row['end_date'].strftime('%Y-%m-%d')}<br>" +
                f"Duration: {row['duration_days']} days<br>" +
                "<extra></extra>"
            )
        ))
    
    fig.update_layout(
        title="Trip Timeline (Recent 20 Trips)",
        xaxis_title="Date",
        yaxis_title="Destination",
        height=500,
        hovermode='closest'
    )
    
    return fig

def create_destination_chart(df):
    """Create a bar chart of destinations"""
    if df.empty:
        return go.Figure().add_annotation(text="No trip data available")
    
    destination_counts = df['destination'].value_counts().head(10)
    
    fig = px.bar(
        x=destination_counts.values,
        y=destination_counts.index,
        orientation='h',
        title="Top 10 Destinations",
        labels={'x': 'Number of Visits', 'y': 'Destination'},
        color=destination_counts.values,
        color_continuous_scale='Blues'
    )
    
    fig.update_layout(height=400, showlegend=False)
    return fig

def create_monthly_chart(df):
    """Create a chart showing trips by month"""
    if df.empty:
        return go.Figure().add_annotation(text="No trip data available")
    
    # Get last 12 months of data
    cutoff_date = datetime.now().replace(tzinfo=None) - timedelta(days=365)
    recent_df = df[df['start_date'] >= cutoff_date]
    
    if recent_df.empty:
        recent_df = df.head(20)  # Fall back to last 20 trips
    
    recent_df['year_month'] = recent_df['start_date'].dt.strftime('%Y-%m')
    monthly_trips = recent_df.groupby('year_month').size().reset_index(name='count')
    monthly_trips = monthly_trips.sort_values('year_month')
    
    fig = px.bar(
        monthly_trips,
        x='year_month',
        y='count',
        title="Trips by Month (Last 12 Months)",
        labels={'count': 'Number of Trips', 'year_month': 'Month'},
        color='count',
        color_continuous_scale='Viridis'
    )
    
    fig.update_layout(height=400, showlegend=False)
    return fig

def main():
    st.title("🗺️ My Travel Dashboard")
    st.markdown("---")
    
    # Instructions
    with st.expander("📖 How to use this app"):
        st.markdown("""
        1. **Export your Apple Calendar:**
           - Open Calendar app on your Mac
           - Select the calendar(s) with your trips
           - Go to File → Export → Export...
           - Save as .ics file
        
        2. **Upload the file below**
        
        3. **View your travel insights!**
        
        The app detects travel events by looking for:
        - Booking platforms (Airbnb, Booking.com, Agoda, Trip.com, etc.)
        - Travel keywords (flight, hotel, trip, vacation, etc.)
        - Travel emojis (✈️, 🏨, etc.)
        """)
    
    # File upload
    uploaded_file = st.file_uploader(
        "Upload your calendar export (.ics file)", 
        type=['ics'],
        help="Export your calendar from Apple Calendar as an .ics file"
    )
    
    if uploaded_file is not None:
        # Process the file
        with st.spinner("Processing your calendar data..."):
            file_content = uploaded_file.read()
            file_hash = get_file_hash(file_content)
            df = process_ics_file(file_hash, file_content)
            
            # Store in session state for future use
            st.session_state['cached_trips'] = df
        
        if df.empty:
            st.warning("No travel-related events found. Make sure your trips contain booking platform names (Airbnb, Booking.com, etc.) or travel keywords.")
            return
        
        # Metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.markdown('<div class="metric-card">', unsafe_allow_html=True)
            st.markdown("📊 **Total Trips**")
            st.markdown(f'<div class="metric-value" style="color: #1f77b4;">{len(df)}</div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)
        
        with col2:
            st.markdown('<div class="metric-card">', unsafe_allow_html=True)
            st.markdown("✈️ **Unique Destinations**")
            st.markdown(f'<div class="metric-value" style="color: #2ca02c;">{df["destination"].nunique()}</div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)
        
        with col3:
            st.markdown('<div class="metric-card">', unsafe_allow_html=True)
            st.markdown("📅 **Total Travel Days**")
            st.markdown(f'<div class="metric-value" style="color: #ff7f0e;">{df["duration_days"].sum()}</div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)
        
        with col4:
            current_date = datetime.now().replace(tzinfo=None)
            future_trips = df[df['start_date'] > current_date]
            if not future_trips.empty:
                next_trip = future_trips.iloc[0]
                days_until = (next_trip['start_date'] - datetime.now()).days
                next_trip_text = f"{next_trip['destination']}<br>in {days_until} days"
            else:
                next_trip_text = "No upcoming trips"
            
            st.markdown('<div class="metric-card">', unsafe_allow_html=True)
            st.markdown("🌍 **Next Trip**")
            st.markdown(f'<div class="metric-value" style="color: #d62728; font-size: 1.5em;">{next_trip_text}</div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)
        
        # Visualizations
        st.markdown("---")
        
        # Timeline
        st.plotly_chart(create_timeline_chart(df), use_container_width=True)
        
        # Two columns for charts
        col1, col2 = st.columns(2)
        
        with col1:
            st.plotly_chart(create_destination_chart(df), use_container_width=True)
        
        with col2:
            st.plotly_chart(create_monthly_chart(df), use_container_width=True)
            
        # Add interactive map
        st.markdown("---")
        render_trip_map_fast(df)
        
        # Trip details section continues below...
        st.markdown("---")
        
        # Trip details
        st.markdown("---")
        st.subheader("📋 Trip Details")
        
        # Add filter options
        col1, col2, col3 = st.columns(3)
        
        with col1:
            # Filter by destination
            destinations = ['All'] + sorted(df['destination'].unique().tolist())
            selected_destination = st.selectbox('Filter by Destination', destinations)
        
        with col2:
            # Filter by year
            df['year'] = df['start_date'].dt.year
            years = ['All'] + sorted(df['year'].unique().tolist(), reverse=True)
            selected_year = st.selectbox('Filter by Year', years)
        
        with col3:
            # Sort order
            sort_order = st.selectbox('Sort by', ['Most Recent', 'Oldest First', 'Longest Duration', 'Destination A-Z'])
        
        # Apply filters
        filtered_df = df.copy()
        
        if selected_destination != 'All':
            filtered_df = filtered_df[filtered_df['destination'] == selected_destination]
        
        if selected_year != 'All':
            filtered_df = filtered_df[filtered_df['year'] == selected_year]
        
        # Apply sorting
        if sort_order == 'Most Recent':
            filtered_df = filtered_df.sort_values('start_date', ascending=False)
        elif sort_order == 'Oldest First':
            filtered_df = filtered_df.sort_values('start_date', ascending=True)
        elif sort_order == 'Longest Duration':
            filtered_df = filtered_df.sort_values('duration_days', ascending=False)
        else:  # Destination A-Z
            filtered_df = filtered_df.sort_values('destination', ascending=True)
        
        # Format the dataframe for display
        display_df = filtered_df[['title', 'destination', 'start_date', 'end_date', 'duration_days']].copy()
        display_df['start_date'] = display_df['start_date'].dt.strftime('%Y-%m-%d')
        display_df['end_date'] = display_df['end_date'].dt.strftime('%Y-%m-%d')
        display_df.columns = ['Trip', 'Destination', 'Start Date', 'End Date', 'Days']
        
        # Show filtered results count
        st.info(f"Showing {len(display_df)} trips")
        
        # Display the dataframe
        st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True
        )
        
        # Download options
        st.markdown("---")
        st.subheader("📥 Download Your Data")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Download filtered data as CSV
            csv = display_df.to_csv(index=False)
            st.download_button(
                label="Download Filtered Trips (CSV)",
                data=csv,
                file_name=f"my_trips_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )
        
        with col2:
            # Download summary statistics
            summary_data = {
                'Metric': ['Total Trips', 'Unique Destinations', 'Total Travel Days', 'Average Trip Duration', 'Most Visited Destination'],
                'Value': [
                    len(df),
                    df['destination'].nunique(),
                    df['duration_days'].sum(),
                    f"{df['duration_days'].mean():.1f} days",
                    f"{df['destination'].value_counts().index[0]} ({df['destination'].value_counts().iloc[0]} times)"
                ]
            }
            summary_df = pd.DataFrame(summary_data)
            summary_csv = summary_df.to_csv(index=False)
            
            st.download_button(
                label="Download Summary Statistics (CSV)",
                data=summary_csv,
                file_name=f"trip_summary_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )
    
    else:
        # Show demo/placeholder when no file is uploaded
        st.info("👆 Upload your calendar .ics file to get started!")
        
        # Show sample visualization with dummy data
        st.subheader("Sample Visualization")
        
        col1, col2 = st.columns(2)
        
        with col1:
            sample_destinations = pd.DataFrame({
                'destination': ['Paris', 'Tokyo', 'New York', 'London', 'Barcelona'],
                'trips': [3, 2, 4, 2, 1]
            })
            fig = px.bar(
                sample_destinations, 
                x='trips', 
                y='destination', 
                orientation='h',
                title="Sample: Top Destinations", 
                color='trips',
                color_continuous_scale='Blues'
            )
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            sample_monthly = pd.DataFrame({
                'month': ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun'],
                'trips': [1, 0, 2, 1, 3, 2]
            })
            fig = px.bar(
                sample_monthly,
                x='month',
                y='trips',
                title="Sample: Monthly Travel Frequency",
                color='trips',
                color_continuous_scale='Viridis'
            )
            st.plotly_chart(fig, use_container_width=True)
        
        # Add helpful tips
        st.markdown("---")
        st.subheader("💡 Tips for Better Results")
        st.markdown("""
        - **Add booking platform names** to your calendar events (e.g., "Airbnb: Beach House Miami")
        - **Include location information** in the location field of your events
        - **Use travel-related keywords** in event titles (flight, hotel, trip, etc.)
        - **Add travel emojis** to make detection easier (✈️, 🏨, 🏖️)
        - **Be consistent** with destination names for better grouping
        """)

if __name__ == "__main__":
    main()
