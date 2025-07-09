import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
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
    # Read the ICS file
    ics_content = uploaded_file.read()
    cal = icalendar.Calendar.from_ical(ics_content)
    
    # Keywords that might indicate travel
    travel_keywords = [
        'flight', 'hotel', 'airbnb', 'trip', 'travel', 'vacation',
        'holiday', 'visit', 'tour', 'cruise', 'train', 'bus',
        'rental car', 'airport', 'checkin', 'checkout', 'reservation',
        'booking', '✈️', '🏨', '🚂', '🚗', '🏖️', '🗺️'
    ]
    
    trips = []
    
    for component in cal.walk():
        if component.name == "VEVENT":
            summary = str(component.get('summary', ''))
            location = str(component.get('location', ''))
            description = str(component.get('description', ''))
            
            # Check if this might be a travel event
            combined_text = (summary + " " + location + " " + description).lower()
            
            if any(keyword in combined_text for keyword in travel_keywords):
                start = component.get('dtstart')
                end = component.get('dtend')
                
                # Handle different date formats
                if start:
                    start_date = start.dt if hasattr(start, 'dt') else start
                    if isinstance(start_date, datetime):
                        start_date = start_date
                    else:
                        start_date = datetime.combine(start_date, datetime.min.time())
                
                if end:
                    end_date = end.dt if hasattr(end, 'dt') else end
                    if isinstance(end_date, datetime):
                        end_date = end_date
                    else:
                        end_date = datetime.combine(end_date, datetime.min.time())
                else:
                    end_date = start_date
                
                trip_data = {
                    'title': summary,
                    'start_date': start_date,
                    'end_date': end_date,
                    'location': location,
                    'description': description,
                    'destination': extract_destination(summary, location)
                }
                trips.append(trip_data)
    
    df = pd.DataFrame(trips)
    if not df.empty:
        df['duration_days'] = (df['end_date'] - df['start_date']).dt.days + 1
        df = df.sort_values('start_date')
    
    return df

def extract_destination(title, location):
    """Try to extract destination from title and location"""
    # Common patterns for destinations
    patterns = [
        r'to\s+([A-Z][a-zA-Z\s]+)',
        r'in\s+([A-Z][a-zA-Z\s]+)',
        r'at\s+([A-Z][a-zA-Z\s]+)',
        r'-\s+([A-Z][a-zA-Z\s]+)',
        r':\s+([A-Z][a-zA-Z\s]+)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, title)
        if match:
            return match.group(1).strip()
    
    # If location exists and seems like a place
    if location and len(location) > 2:
        return location.split(',')[0].strip()
    
    # Default to extracting from title
    words = title.split()
    for word in words:
        if word and word[0].isupper() and len(word) > 2:
            return word
    
    return "Unknown"

def create_timeline_chart(df):
    """Create a timeline visualization of trips"""
    if df.empty:
        return go.Figure().add_annotation(text="No trip data available")
    
    # Create a Gantt-like chart
    fig = go.Figure()
    
    # Sort by start date and assign y-positions
    df_sorted = df.sort_values('start_date')
    df_sorted['y_pos'] = range(len(df_sorted))
    
    for idx, row in df_sorted.iterrows():
        fig.add_trace(go.Scatter(
            x=[row['start_date'], row['end_date']],
            y=[row['y_pos'], row['y_pos']],
            mode='lines+markers',
            name=row['destination'],
            line=dict(width=10),
            marker=dict(size=10),
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
        title="Trip Timeline",
        xaxis_title="Date",
        yaxis_title="Trips",
        height=400,
        showlegend=False,
        yaxis=dict(
            tickmode='array',
            tickvals=df_sorted['y_pos'].tolist(),
            ticktext=df_sorted['destination'].tolist()
        )
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
        title="Top Destinations",
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
    
    df['year_month'] = df['start_date'].dt.to_period('M').astype(str)
    monthly_trips = df.groupby('year_month').size().reset_index(name='count')
    
    fig = px.bar(
        monthly_trips,
        x='year_month',
        y='count',
        title="Trips by Month",
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
        
        The app will automatically detect travel-related events based on keywords like 
        'flight', 'hotel', 'trip', etc.
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
            df = process_ics_file(uploaded_file)
        
        if df.empty:
            st.warning("No travel-related events found in your calendar. Try adjusting your calendar export or check if your trips have keywords like 'flight', 'hotel', 'trip', etc.")
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
            future_trips = df[df['start_date'] > datetime.now()]
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
        
        # Trip details
        st.markdown("---")
        st.subheader("📋 Trip Details")
        
        # Format the dataframe for display
        display_df = df[['title', 'destination', 'start_date', 'end_date', 'duration_days']].copy()
        display_df['start_date'] = display_df['start_date'].dt.strftime('%Y-%m-%d')
        display_df['end_date'] = display_df['end_date'].dt.strftime('%Y-%m-%d')
        
        st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True
        )
        
        # Download processed data
        csv = display_df.to_csv(index=False)
        st.download_button(
            label="📥 Download trip data as CSV",
            data=csv,
            file_name=f"my_trips_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv"
        )
    
    else:
        # Show demo/placeholder
        st.info("👆 Upload your calendar .ics file to get started!")
        
        # Show sample visualization with dummy data
        st.subheader("Sample Visualization")
        sample_data = pd.DataFrame({
            'destination': ['Paris', 'Tokyo', 'New York', 'London', 'Barcelona'],
            'trips': [3, 2, 4, 2, 1]
        })
        fig = px.bar(sample_data, x='trips', y='destination', orientation='h',
                     title="Sample: Top Destinations", color='trips')
        st.plotly_chart(fig, use_container_width=True)

if __name__ == "__main__":
    main()
