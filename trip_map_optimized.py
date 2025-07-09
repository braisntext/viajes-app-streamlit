import folium
import pandas as pd
from datetime import datetime
import streamlit as st
from streamlit_folium import st_folium
import json
import os

class OptimizedTripMap:
    def __init__(self):
        # Pre-defined coordinates for common destinations to avoid geocoding
        self.coordinates_cache = self.load_coordinates_cache()
    
    def load_coordinates_cache(self):
        """Load cached coordinates from file if exists"""
        cache_file = 'coordinates_cache.json'
        if os.path.exists(cache_file):
            with open(cache_file, 'r') as f:
                return json.load(f)
        
        # Common city coordinates to avoid geocoding
        return {
            # Major cities - add more as needed
            "New York": [40.7128, -74.0060],
            "London": [51.5074, -0.1278],
            "Paris": [48.8566, 2.3522],
            "Tokyo": [35.6762, 139.6503],
            "Barcelona": [41.3851, 2.1734],
            "Rome": [41.9028, 12.4964],
            "Berlin": [52.5200, 13.4050],
            "Madrid": [40.4168, -3.7038],
            "Amsterdam": [52.3676, 4.9041],
            "Prague": [50.0755, 14.4378],
            "Vienna": [48.2082, 16.3738],
            "Bangkok": [13.7563, 100.5018],
            "Singapore": [1.3521, 103.8198],
            "Dubai": [25.2048, 55.2708],
            "Sydney": [-33.8688, 151.2093],
            "Miami": [25.7617, -80.1918],
            "Los Angeles": [34.0522, -118.2437],
            "San Francisco": [37.7749, -122.4194],
            "Chicago": [41.8781, -87.6298],
            "Boston": [42.3601, -71.0589],
        }
    
    def get_coordinates_fast(self, destination):
        """Get coordinates using cache first, then simple approximation"""
        # Clean destination name
        dest_clean = destination.strip().title()
        
        # Check cache
        if dest_clean in self.coordinates_cache:
            return self.coordinates_cache[dest_clean]
        
        # Check partial matches
        for cached_dest, coords in self.coordinates_cache.items():
            if cached_dest.lower() in dest_clean.lower() or dest_clean.lower() in cached_dest.lower():
                return coords
        
        # If not in cache, use a simple approximation based on continent
        # This is faster than geocoding but less accurate
        # You can expand this logic based on your travel patterns
        if any(country in destination.lower() for country in ['usa', 'united states', 'america']):
            return [39.8283, -98.5795]  # Center of USA
        elif any(country in destination.lower() for country in ['uk', 'england', 'britain']):
            return [54.0000, -2.0000]  # Center of UK
        elif any(country in destination.lower() for country in ['spain', 'españa']):
            return [40.4637, -3.7492]  # Center of Spain
        
        # Default to a central location
        return [48.8566, 2.3522]  # Paris as default
    
    def create_map_fast(self, df):
        """Create map without geocoding delays"""
        if df.empty:
            return None
        
        # Get current date
        current_date = datetime.now().replace(tzinfo=None)
        
        # Add status and coordinates
        df = df.copy()
        df['status'] = df.apply(lambda row: self._get_status(row, current_date), axis=1)
        df['coordinates'] = df['destination'].apply(self.get_coordinates_fast)
        
        # Calculate center
        all_coords = df['coordinates'].tolist()
        center_lat = sum(coord[0] for coord in all_coords) / len(all_coords)
        center_lon = sum(coord[1] for coord in all_coords) / len(all_coords)
        
        # Create map
        m = folium.Map(
            location=[center_lat, center_lon],
            zoom_start=3,
            tiles='CartoDB positron',
            prefer_canvas=True  # Faster rendering
        )
        
        # Sort by date
        df_sorted = df.sort_values('start_date').reset_index(drop=True)
        
        # Add markers only (no lines initially for performance)
        for idx, row in df_sorted.iterrows():
            # Determine color
            if row['status'] == 'past':
                color = 'lightgreen'
            elif row['status'] == 'current':
                color = 'lightred'
            else:
                color = 'orange'
            
            # Simple popup
            popup_html = f"""
            <div style='width: 180px;'>
                <b>{row['destination']}</b><br>
                {row['start_date'].strftime('%b %d, %Y')}<br>
                <a href='https://www.google.com/maps/search/{row['destination']}' target='_blank'>Open in Maps</a>
            </div>
            """
            
            folium.CircleMarker(
                location=row['coordinates'],
                radius=8,
                popup=folium.Popup(popup_html, max_width=200),
                tooltip=row['destination'],
                color=color,
                fill=True,
                fillColor=color,
                fillOpacity=0.7
            ).add_to(m)
        
        # Add simple legend
        legend_html = '''
        <div style="position: fixed; 
                    top: 10px; right: 10px; width: 150px; height: 100px; 
                    background-color: white; z-index:9999; font-size:12px;
                    border:1px solid grey; border-radius: 5px; padding: 10px">
            <b>Trip Status</b><br>
            <span style="color: green;">●</span> Past<br>
            <span style="color: red;">●</span> Current<br>
            <span style="color: orange;">●</span> Future
        </div>
        '''
        m.get_root().html.add_child(folium.Element(legend_html))
        
        # Save coordinates cache
        self.save_coordinates_cache()
        
        return m
    
    def save_coordinates_cache(self):
        """Save coordinates cache to file"""
        with open('coordinates_cache.json', 'w') as f:
            json.dump(self.coordinates_cache, f)
    
    def _get_status(self, row, current_date):
        """Determine if trip is past, current, or future"""
        if row['end_date'] < current_date:
            return 'past'
        elif row['start_date'] <= current_date <= row['end_date']:
            return 'current'
        else:
            return 'future'

def render_trip_map_fast(df):
    """Render optimized trip map"""
    st.subheader("🗺️ Trip Map (Fast View)")
    
    # Add a toggle for full features
    use_full_map = st.checkbox("Enable hover connections (slower)", value=False)
    
    if use_full_map:
        # Import and use the full-featured map
        from trip_map import render_trip_map
        render_trip_map(df)
    else:
        # Use the optimized version
        with st.spinner("Creating map..."):
            trip_map = OptimizedTripMap()
            m = trip_map.create_map_fast(df)
            
            if m:
                st_folium(
                    m, 
                    key="trip_map_fast",
                    width=None,
                    height=500
                )
                
                st.info("💡 Tip: Enable 'hover connections' above for interactive trip connections")
