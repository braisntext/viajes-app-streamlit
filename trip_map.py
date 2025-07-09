import folium
from folium import plugins
import pandas as pd
from datetime import datetime
import streamlit as st
from streamlit_folium import st_folium
import webbrowser
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut
import time

class TripMap:
    def __init__(self):
        self.geolocator = Nominatim(user_agent="trip-visualizer")
        self.location_cache = {}
    
    def get_coordinates(self, destination):
        """Get coordinates for a destination with caching"""
        if destination in self.location_cache:
            return self.location_cache[destination]
        
        try:
            time.sleep(1)  # Respect rate limits
            location = self.geolocator.geocode(destination)
            if location:
                coords = (location.latitude, location.longitude)
                self.location_cache[destination] = coords
                return coords
        except GeocoderTimedOut:
            return None
        except Exception as e:
            st.warning(f"Could not geocode {destination}")
            return None
        
        return None
    
    def create_map(self, df):
        """Create an interactive map with trip locations"""
        if df.empty:
            return None
        
        # Get current date
        current_date = datetime.now().replace(tzinfo=None)
        
        # Add status column
        df['status'] = df.apply(lambda row: self._get_status(row, current_date), axis=1)
        
        # Get coordinates for each destination
        df['coordinates'] = df['destination'].apply(self.get_coordinates)
        
        # Filter out destinations without coordinates
        df_with_coords = df[df['coordinates'].notna()].copy()
        
        if df_with_coords.empty:
            st.warning("Could not find coordinates for any destinations")
            return None
        
        # Create base map
        center_lat = sum(coord[0] for coord in df_with_coords['coordinates']) / len(df_with_coords)
        center_lon = sum(coord[1] for coord in df_with_coords['coordinates']) / len(df_with_coords)
        
        m = folium.Map(
            location=[center_lat, center_lon],
            zoom_start=3,
            tiles='CartoDB positron'
        )
        
        # Sort by date for connecting lines
        df_sorted = df_with_coords.sort_values('start_date')
        
        # Add markers with hover-activated connections
        for idx in range(len(df_sorted)):
            row = df_sorted.iloc[idx]
            
            # Determine color based on status
            if row['status'] == 'past':
                color = 'lightgreen'
                icon_color = 'green'
            elif row['status'] == 'current':
                color = 'lightred'
                icon_color = 'red'
            else:  # future
                color = 'orange'
                icon_color = 'orange'
            
            # Create popup content
            popup_html = f"""
            <div style='width: 200px;'>
                <h4>{row['destination']}</h4>
                <p><b>{row['title']}</b></p>
                <p>📅 {row['start_date'].strftime('%Y-%m-%d')} to {row['end_date'].strftime('%Y-%m-%d')}</p>
                <p>⏱️ {row['duration_days']} days</p>
                <p><a href='https://www.google.com/maps/search/{row['destination']}' target='_blank'>Open in Google Maps 🗺️</a></p>
            </div>
            """
            
            # Add marker
            marker = folium.Marker(
                location=row['coordinates'],
                popup=folium.Popup(popup_html, max_width=250),
                tooltip=f"{row['destination']} ({row['start_date'].strftime('%b %Y')})",
                icon=folium.Icon(color=color, icon='info-sign')
            )
            marker.add_to(m)
        
        # Add all connections as hidden polylines
        for idx in range(len(df_sorted)):
            row = df_sorted.iloc[idx]
            
            # Connection to previous trip (dotted)
            if idx > 0:
                prev_row = df_sorted.iloc[idx - 1]
                folium.PolyLine(
                    locations=[prev_row['coordinates'], row['coordinates']],
                    color='gray',
                    weight=2,
                    opacity=0,  # Start hidden
                    dash_array='5, 10',  # Dotted line
                    class_name=f'connection-{idx}-prev'
                ).add_to(m)
            
            # Connection to next trip (solid)
            if idx < len(df_sorted) - 1:
                next_row = df_sorted.iloc[idx + 1]
                folium.PolyLine(
                    locations=[row['coordinates'], next_row['coordinates']],
                    color='blue',
                    weight=2,
                    opacity=0,  # Start hidden
                    class_name=f'connection-{idx}-next'
                ).add_to(m)
            
        
        # Add legend
        legend_html = '''
        <div style="position: fixed; 
                    top: 10px; right: 10px; width: 200px; height: 120px; 
                    background-color: white; z-index:9999; font-size:14px;
                    border:2px solid grey; border-radius: 5px; padding: 10px">
            <p style="margin: 0;"><b>Trip Status</b></p>
            <p style="margin: 5px 0;"><span style="color: green;">●</span> Past trips</p>
            <p style="margin: 5px 0;"><span style="color: red;">●</span> Current trip</p>
            <p style="margin: 5px 0;"><span style="color: orange;">●</span> Future trips</p>
            <hr style="margin: 5px 0;">
            <p style="margin: 5px 0; font-size: 12px;">Hover over markers to see connections</p>
            <p style="margin: 5px 0; font-size: 12px;">Click for details & Google Maps</p>
        </div>
        '''
        m.get_root().html.add_child(folium.Element(legend_html))

        # Add custom JavaScript for hover effects
        hover_script = f"""
        <script>
        document.addEventListener('DOMContentLoaded', function() {{
            setTimeout(function() {{
                var markers = document.querySelectorAll('.leaflet-marker-icon');
                var polylines = document.querySelectorAll('.leaflet-interactive');
                
                markers.forEach(function(marker, markerIndex) {{
                    marker.addEventListener('mouseenter', function() {{
                        polylines.forEach(function(polyline) {{
                            var className = polyline.getAttribute('class');
                            if (className && className.includes('connection-' + markerIndex)) {{
                                polyline.style.opacity = '0.7';
                            }}
                        }});
                    }});
                    
                    marker.addEventListener('mouseleave', function() {{
                        polylines.forEach(function(polyline) {{
                            if (polyline.getAttribute('class') && polyline.getAttribute('class').includes('connection-')) {{
                                polyline.style.opacity = '0';
                            }}
                        }});
                    }});
                }});
            }}, 1000);
        }});
        </script>
        """
        m.get_root().html.add_child(folium.Element(hover_script))
        
        return m
    
    def _get_status(self, row, current_date):
        """Determine if trip is past, current, or future"""
        if row['end_date'] < current_date:
            return 'past'
        elif row['start_date'] <= current_date <= row['end_date']:
            return 'current'
        else:
            return 'future'

def render_trip_map(df):
    """Render the trip map in Streamlit"""
    st.subheader("🗺️ Interactive Trip Map")
    
    with st.spinner("Creating map..."):
        trip_map = TripMap()
        m = trip_map.create_map(df)
        
        if m:
            # Display the map
            map_data = st_folium(
                m, 
                key="trip_map",
                returned_objects=["last_object_clicked"],
                width=None,
                height=600
            )
            
            # Show info about clicked location
            if map_data['last_object_clicked'] and map_data['last_object_clicked']['popup']:
                st.info("Click on any marker to see trip details and open in Google Maps")
        else:
            st.error("Could not create map. Please check your destinations.")
