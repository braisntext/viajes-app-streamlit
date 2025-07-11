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
            # Japanese cities and areas
            "Fukuoka": [33.5904, 130.4017],
            "Yanagawa": [33.1633, 130.4056],
            "Hiroshima": [34.3853, 132.4553],
            "Miyajima": [34.2956, 132.3195],
            "Nishifujinomoricho": [34.9877, 135.7529],  # Kyoto area
            "Murasakino": [35.0377, 135.7529],  # Kyoto area
            "Shinosaka": [34.7338, 135.5004],  # Osaka area
            "Nishiwajir": [35.6762, 139.6503],  # Tokyo area
            "Beppu": [33.2846, 131.4910],
            "Daiiti": [33.2396, 131.6093],  # Beppu area
            "Noreply": [35.6762, 139.6503],  # Default to Tokyo
            "East 21 Tokyo": [35.6762, 139.6503],
        }
    
    def get_coordinates_fast(self, destination, location_field=''):
        """Get coordinates using URLs first, then cache, then approximation"""
        
        # First, try to extract from Google Maps or Trip.com URLs in location field
        if location_field:
            # Google Maps patterns
            import re
            
            # Pattern for Google Maps URLs with coordinates
            google_patterns = [
                r'@([-\d.]+),([-\d.]+)',  # @lat,lng format
                r'll=([-\d.]+),([-\d.]+)',  # ll=lat,lng format
                r'q=([-\d.]+),([-\d.]+)',  # q=lat,lng format
            ]
            
            for pattern in google_patterns:
                match = re.search(pattern, location_field)
                if match:
                    try:
                        lat = float(match.group(1))
                        lon = float(match.group(2))
                        # Save to cache for future use
                        self.coordinates_cache[destination] = [lat, lon]
                        return [lat, lon]
                    except:
                        pass
            
            # Trip.com coordinates pattern (if they use a specific format)
            trip_patterns = [
                r'latitude["\']?\s*:\s*([-\d.]+).*longitude["\']?\s*:\s*([-\d.]+)',
                r'lat["\']?\s*:\s*([-\d.]+).*lng["\']?\s*:\s*([-\d.]+)',
            ]
            
            for pattern in trip_patterns:
                match = re.search(pattern, location_field, re.IGNORECASE | re.DOTALL)
                if match:
                    try:
                        lat = float(match.group(1))
                        lon = float(match.group(2))
                        self.coordinates_cache[destination] = [lat, lon]
                        return [lat, lon]
                    except:
                        pass
        
        # Clean destination name
        dest_clean = destination.strip().title()
        
        # Check cache
        if dest_clean in self.coordinates_cache:
            return self.coordinates_cache[dest_clean]
        
        # For Japanese destinations, add specific handling
        japan_cities = {
            "Matsubaya": [34.6937, 135.5023],  # Osaka
            "Osaka": [34.6937, 135.5023],
            "Kyoto": [35.0116, 135.7681],
            "Tokyo": [35.6762, 139.6503],
            "Hiroshima": [34.3853, 132.4553],
            "Nagasaki": [32.7503, 129.8777],
            "Fukuoka": [33.5904, 130.4017],
            "Sapporo": [43.0642, 141.3469],
            "Nara": [34.6851, 135.8048],
            "Yokohama": [35.4437, 139.6380],
        }
        
        # Check Japanese cities
        for city, coords in japan_cities.items():
            if city.lower() in destination.lower():
                return coords
        
        # Check partial matches in main cache
        for cached_dest, coords in self.coordinates_cache.items():
            if cached_dest.lower() in dest_clean.lower() or dest_clean.lower() in cached_dest.lower():
                return coords
        
        # If destination contains "Ryokan" or Japanese-style names, default to Japan center
        if any(word in destination.lower() for word in ['ryokan', 'onsen', 'shrine', 'temple']):
            return [36.2048, 138.2529]  # Center of Japan
        
        # Original fallback logic
        if any(country in destination.lower() for country in ['usa', 'united states', 'america']):
            return [39.8283, -98.5795]
        elif any(country in destination.lower() for country in ['uk', 'england', 'britain']):
            return [54.0000, -2.0000]
        elif any(country in destination.lower() for country in ['spain', 'españa']):
            return [40.4637, -3.7492]
        elif any(country in destination.lower() for country in ['japan', '日本']):
            return [36.2048, 138.2529]
        
        # Default to asking user or showing unknown
        return None  # Will handle this in create_map_fast
    
    def create_map_fast(self, df):
        """Create map without geocoding delays"""
        if df.empty:
            return None
        
        # Get current date
        current_date = datetime.now().replace(tzinfo=None)
        
        # Add status and coordinates
        df = df.copy()
        df['status'] = df.apply(lambda row: self._get_status(row, current_date), axis=1)
        df['coordinates'] = df.apply(
            lambda row: self.get_coordinates_fast(row['destination'], row.get('location', '')), 
            axis=1
        )

                # Filter out entries without coordinates
        df_with_coords = df[df['coordinates'].notna()].copy()
        
        if df_with_coords.empty:
            st.warning("Could not determine coordinates for any destinations.")
            return None
        
        # Show warning for missing coordinates
        missing_coords = df[df['coordinates'].isna()]
        if not missing_coords.empty:
            st.warning(f"⚠️ Could not determine location for {len(missing_coords)} trips: {', '.join(missing_coords['destination'].head(5).tolist())}")
        
        # Use only trips with coordinates
        df = df_with_coords
        
        # Calculate center
        all_coords = df['coordinates'].tolist()
        center_lat = sum(coord[0] for coord in all_coords) / len(all_coords)
        center_lon = sum(coord[1] for coord in all_coords) / len(all_coords)

        # Adjust zoom based on number of trips
        if len(df) == 1:
            zoom_level = 10
        elif len(df) < 5:
            zoom_level = 6
        elif len(df) < 10:
            zoom_level = 4
        else:
            zoom_level = 3
        
        # Create map
        m = folium.Map(
            location=[center_lat, center_lon],
            zoom_start=zoom_level,  # Use dynamic zoom instead of fixed 3
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
                🛏️ {row['duration_days']} night{'s' if row['duration_days'] != 1 else ''}<br>
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
    
    # Filter buttons
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        show_past = st.button("📅 Show Past Trips", key="show_past", type="secondary")
    with col2:
        show_current_future = st.button("🔄 Current & Future", key="show_current_future", type="primary")
    with col3:
        show_all = st.button("🌍 Show All Trips", key="show_all", type="secondary")
    with col4:
        if st.button("📍 Fix Locations", key="fix_locations"):
            with st.expander("Override coordinates for misplaced locations"):
                st.markdown("""
                Add Google Maps links to your calendar events' location field for accurate placement.
                
                For past events without links, you can manually set coordinates here:
                """)
                
                # Show destinations that might need fixing
                problem_destinations = filtered_df[['destination']].drop_duplicates()
                
                for dest in problem_destinations['destination'].head(10):
                    col_a, col_b, col_c = st.columns([2, 1, 1])
                    with col_a:
                        st.text(dest)
                    with col_b:
                        lat = st.number_input(f"Lat", key=f"lat_{dest}", value=0.0, format="%.4f", label_visibility="collapsed")
                    with col_c:
                        lon = st.number_input(f"Lon", key=f"lon_{dest}", value=0.0, format="%.4f", label_visibility="collapsed")
    
    # Initialize session state for filter
    if 'map_filter' not in st.session_state:
        st.session_state.map_filter = 'current_future'
    
    # Update filter based on button clicks
    if show_past:
        st.session_state.map_filter = 'past'
    elif show_current_future:
        st.session_state.map_filter = 'current_future'
    elif show_all:
        st.session_state.map_filter = 'all'
    
    # Filter the dataframe based on selection
    current_date = datetime.now().replace(tzinfo=None)
    
    if st.session_state.map_filter == 'past':
        filtered_df = df[df['end_date'] < current_date].copy()
        filter_info = f"Showing {len(filtered_df)} past trips"
    elif st.session_state.map_filter == 'current_future':
        filtered_df = df[df['end_date'] >= current_date].copy()
        filter_info = f"Showing {len(filtered_df)} current and future trips"
    else:  # all
        filtered_df = df.copy()
        filter_info = f"Showing all {len(filtered_df)} trips"
    
    # Show filter info
    st.info(f"🔍 {filter_info}")
    
    # Check if there are trips to show
    if filtered_df.empty:
        st.warning("No trips found for the selected filter.")
        return
    
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
            m = trip_map.create_map_fast(filtered_df)  # Use filtered dataframe
            
            if m:
                st_folium(
                    m, 
                    key="trip_map_fast",
                    width=None,
                    height=500
                )
                
                st.info("💡 Tip: Enable 'hover connections' above for interactive trip connections")
