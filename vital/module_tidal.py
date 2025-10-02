"""
module_tidal.py

Tools for working with tidal data, including the `TidalData` class and utility functions.

Functions:
    create_tidal_data(station, startdate, range_hrs, time_step_s): Creates a TidalData instance.
    process_tidal_data(station, startdate, range_hrs, time_step_s, city_data_file): Processes tidal data in one step.

Classes:
    TidalData: A class for retrieving and processing tidal data from NOAA APIs.
    TidalResults: A data class to store the results of tidal data processing.

Raises:
    ValueError: If the city data file is not found or if there is an error processing tidal data.
"""
import requests
import math
import datetime
import calendar
import numpy as np
from scipy.interpolate import PchipInterpolator
import pandas as pd
from dataclasses import dataclass

from vital.constGlobal import ConstantsGlobal
from vital.constUnitConvert import ConstantsUnitConversion

# Constants
GLOBAL = ConstantsGlobal()
CONVERT = ConstantsUnitConversion()

# Constants
NOAA_API_BASE_URL = 'https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations'
NOAA_TIDAL_DATA_URL = 'https://api.tidesandcurrents.noaa.gov/api/prod/datagetter'
EARTH_RADIUS_M = 6378137.0
MIN_FLOW_SPEED = 1e-4
DEFAULT_MOORING_DISTANCE_M = 50.0

class TidalData:
    """
    A class for retrieving and processing tidal data from NOAA APIs.
    """
    def __init__(self, station: str, startdate: str, range_hrs: int, time_step_s: float): 
        """
        Initializes a TidalData instance.

        Args:
            station (str): The NOAA station identifier.
            startdate (str): The start date for tidal data retrieval (format: 'YYYY-MM-DD').
            range_hrs (int): The range of hours for tidal data retrieval.
            time_step_s (float): The time step in seconds for interpolation.

        Attributes:
            station (str): The NOAA station identifier.
            startdate (str): The start date for tidal data retrieval.
            range_hrs (int): The range of hours for tidal data retrieval.
            time_step_s (float): The time step in seconds for interpolation.
            flow_speeds_m_s (np.ndarray): The array of flow speeds in meters per second.
            time_s (np.ndarray): The array of time steps in seconds.
            mooring_distance_m (float): The mooring distance in meters.
            buoy_latitude_rad (float): The latitude of the buoy in radians.
            buoy_longitude_rad (float): The longitude of the buoy in radians.
            station_name (str): The name of the NOAA station.
            nearest_city (str): The name of the nearest city to the buoy.
            electrical_cable_length_m (float): The length of the electrical cable in meters.
            session (requests.Session): The HTTP session used for API requests.
        """
        self.station: str = station
        self.startdate: str = startdate
        self.range_hrs: int = range_hrs
        self.time_step_s: float = time_step_s
        self.flow_speeds_m_s: np.ndarray = None
        self.time_s: np.ndarray = None
        self.mooring_distance_m: float = None
        self.buoy_latitude_rad: float = None
        self.buoy_longitude_rad: float = None
        self.station_name: str = None
        self.nearest_city: str = None
        self.electrical_cable_length_m: float = None
        self.session = requests.Session()  # Use a session for requests

    def __del__(self):
        """
        Closes the HTTP session when the instance is deleted.
        """
        self.session.close()

    def get_station_name(self) -> str:
        """
        Retrieves the name of the NOAA station.

        Returns:
            str: The name of the station.

        Raises:
            requests.RequestException: If there is an error with the HTTP request.
            KeyError: If the response does not contain the expected data.
        """
        url = f'{NOAA_API_BASE_URL}/{self.station}.json'
        try:
            req_data = self.session.get(url, verify=False)
            req_data.raise_for_status()  # Raise an error for bad responses
            input_data = req_data.json()
            return input_data['stations'][0]['name']
        except (requests.RequestException, KeyError) as e:
            print(f"Error retrieving station name: {e}")
            return None

    def get_station_info(self) -> dict:
        """
        Retrieves information about the NOAA station.

        Returns:
            dict: A dictionary containing station information.

        Raises:
            requests.RequestException: If there is an error with the HTTP request.
            KeyError: If the response does not contain the expected data.
        """
        url = f"{NOAA_API_BASE_URL}/{self.station}.json"
        try:
            req_data = self.session.get(url, verify=False)
            req_data.raise_for_status()
            return req_data.json()
        except (requests.RequestException, KeyError) as e:
            print(f"Error retrieving station info: {e}")
            return {}

    def get_deployment_info(self) -> dict:
        """
        Retrieves deployment information for the station.

        Returns:
            dict: Deployment information, or an empty dictionary if an error occurs.
        """
        url = f"{NOAA_API_BASE_URL}/{self.station}/deployments.json"
        try:
            req_data = self.session.get(url, verify=False)
            req_data.raise_for_status()
            return req_data.json()
        except (requests.RequestException, KeyError) as e:
            print(f"Error retrieving deployment info: {e}")
            return {}

    def get_tidal_data(self) -> dict:
        """
        Retrieves tidal data for the NOAA station.

        Returns:
            dict: A dictionary containing tidal data.

        Raises:
            requests.RequestException: If there is an error with the HTTP request.
            KeyError: If the response does not contain the expected data.
        """
        range_hrs_extended = self.range_hrs + 2
        url = (f'{NOAA_TIDAL_DATA_URL}?station={self.station}&begin_date={self.startdate}&range={range_hrs_extended}'
               f'&product=currents_predictions&units=metric&time_zone=gmt&interval=1&vel_type=speed_dir&format=json')
        try:
            req_data = self.session.get(url, verify=False)
            req_data.raise_for_status()
            return req_data.json()
        except (requests.RequestException, KeyError) as e:
            print(f"Error retrieving tidal data: {e}")
            return {}

    def extract_tidal_speed(self, input_data: dict) -> list:
        """
        Extracts tidal speed data from the input data.

        Args:
            input_data (dict): The dictionary containing tidal data retrieved from NOAA APIs.

        Returns:
            list: A list of tidal speed values extracted from the input data.
        """
        if self.station.lower().startswith('pct'):
            return [x['Velocity_Major'] for x in input_data['current_predictions']['cp']]
        else:
            return [x['Speed'] for x in input_data['current_predictions']['cp']]

    def extract_tidal_time(self, input_data: dict) -> list:
        """
        Extracts tidal time data from the input data.

        Args:
            input_data (dict): The dictionary containing tidal data retrieved from NOAA APIs.

        Returns:
            list: A list of timestamps (in seconds since epoch) extracted from the input data.
        """
        tidal_time_string = [x['Time'] for x in input_data['current_predictions']['cp']]
        date_obj = [datetime.datetime.strptime(x, '%Y-%m-%d %H:%M') for x in tidal_time_string]
        return [calendar.timegm(x.timetuple()) for x in date_obj]

    def distance(self, lat1: float, lat2: float, lon1: float, lon2: float) -> float:
        """
        Calculates the great-circle distance between two points on the Earth.

        Args:
            lat1 (float): The latitude of the first point in radians.
            lat2 (float): The latitude of the second point in radians.
            lon1 (float): The longitude of the first point in radians.
            lon2 (float): The longitude of the second point in radians.

        Returns:
            float: The great-circle distance between the two points in meters.
        """
        dlon = lon2 - lon1
        dlat = lat2 - lat1
        a = math.sin(dlat / 2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2)**2
        c = 2 * math.asin(math.sqrt(a))
        return c * EARTH_RADIUS_M

    def calCableLen(self, buoylat: float, buoylon: float, citytextfile: str) -> tuple:
        """
        Calculates the cable length from the buoy to the nearest city.

        Args:
            buoylat (float): The latitude of the buoy in radians.
            buoylon (float): The longitude of the buoy in radians.
            citytextfile (str): The path to the text file containing city data.

        Returns:
            tuple: A tuple containing:
                cable_length (float): The length of the cable in meters.
                nearest_city (str): The name of the nearest city to the buoy.
        """
        datafile = pd.read_table(citytextfile, delimiter=",", comment='#')
        d_cable_len = np.zeros(len(datafile))
        
        for ind in datafile.index:
            city_lat = math.radians(datafile[datafile.columns[1]][ind])
            city_lon = math.radians(datafile[datafile.columns[2]][ind])

            d_cable_len[ind] = self.distance(buoylat, city_lat, buoylon, city_lon)

        closestCity = datafile[datafile.columns[0]][np.argmin(d_cable_len)]
        cableLen_m = round(d_cable_len[np.argmin(d_cable_len)], 2)
        return cableLen_m, closestCity

    def load_tidal_data(self, city_data_file: str) -> tuple:
        """
        Loads tidal data and calculates the necessary attributes.

        Args:
            city_data_file (str): The path to the text file containing city data, including latitude, longitude, and city names.

        Returns:
            tuple: A tuple containing:
                flow_speeds (np.ndarray): The array of flow speeds in meters per second.
                times (np.ndarray): The array of time steps in seconds.
                mooring_distance (float): The mooring distance in meters.
                latitude (float): The latitude of the buoy in radians.
                longitude (float): The longitude of the buoy in radians.
                station_name (str): The name of the NOAA station.
                nearest_city (str): The name of the nearest city to the buoy.
                cable_length (float): The length of the electrical cable in meters.

        Raises:
            ValueError: If the city data file is not found or if there is an error processing tidal data.
        """
        self.station_name = self.get_station_name()

        if self.station.lower().startswith('pct'):
            input_data = self.get_station_info()
            self.buoy_latitude_rad = math.radians(input_data['stations'][0]['lat'])
            self.buoy_longitude_rad = math.radians(input_data['stations'][0]['lng'])
            self.mooring_distance_m = DEFAULT_MOORING_DISTANCE_M
        else:
            input_data = self.get_deployment_info()
            self.mooring_distance_m = float(input_data['depth'])
            if input_data['units'] == 'feet':
                self.mooring_distance_m *= CONVERT.ft2m
            self.buoy_latitude_rad = math.radians(float(input_data['deployments'][0]['lat']))
            self.buoy_longitude_rad = math.radians(float(input_data['deployments'][0]['lng']))

        tidal_data = self.get_tidal_data()
        tidal_speed_cms = self.extract_tidal_speed(tidal_data)
        tidal_time_s = np.array(self.extract_tidal_time(tidal_data))
        tidal_speed_ms = np.array([float(x) for x in tidal_speed_cms]) * CONVERT.cms2ms

        tidal_CubicSpline = PchipInterpolator(tidal_time_s - tidal_time_s[0], tidal_speed_ms)
        end_time = self.range_hrs * 3600.0
        self.time_s = np.arange(0, end_time, self.time_step_s)
        self.flow_speeds_m_s = tidal_CubicSpline(self.time_s)
        self.flow_speeds_m_s = np.abs(self.flow_speeds_m_s)
        self.flow_speeds_m_s = np.maximum(self.flow_speeds_m_s, MIN_FLOW_SPEED)

        self.electrical_cable_length_m, self.nearest_city = self.calCableLen(self.buoy_latitude_rad, self.buoy_longitude_rad, city_data_file)

        return self.flow_speeds_m_s, self.time_s, self.mooring_distance_m, self.buoy_latitude_rad, self.buoy_longitude_rad, self.station_name, self.nearest_city, self.electrical_cable_length_m

def create_tidal_data(station: str, startdate: str, range_hrs: int, time_step_s: float) -> TidalData:
    """
    Creates and initializes a TidalData instance.

    Args:
        station (str): The NOAA station identifier.
        startdate (str): The start date for tidal data retrieval (format: 'YYYY-MM-DD').
        range_hrs (int): The range of hours for tidal data retrieval.
        time_step_s (float): The time step in seconds for interpolation.

    Returns:
        TidalData: The initialized instance of the TidalData class.
    """
    return TidalData(station, startdate, range_hrs, time_step_s)

def process_tidal_data(
    station: str,
    startdate: str,
    range_hrs: int = 2 * 7 * 24,  # Default: 2 weeks
    time_step_s: int = 3600,  # Default: 1 hour
    city_data_file: str = "../data/AlaskaCityLatLong.txt"
) -> tuple:
    """
    Processes tidal data in one step.

    Args:
        station (str): The NOAA station identifier (e.g., "SEA0801").
        startdate (str): The start date for tidal data retrieval (format: 'YYYY-MM-DD').
        range_hrs (int, optional): The range of hours for tidal data retrieval. Default is 2 weeks.
        time_step_s (int, optional): The time step in seconds for interpolation. Default is 1 hour.
        city_data_file (str, optional): The path to the city data file containing latitude, longitude, and city names.

    Returns:
        tuple: A tuple containing:
            flow_speeds (np.ndarray): The array of flow speeds in meters per second.
            times (np.ndarray): The array of time steps in seconds.
            mooring_distance (float): The mooring distance in meters.
            latitude (float): The latitude of the buoy in radians.
            longitude (float): The longitude of the buoy in radians.
            station_name (str): The name of the NOAA station.
            nearest_city (str): The name of the nearest city to the buoy.
            cable_length (float): The length of the electrical cable in meters.

    Raises:
        ValueError: If the city data file is not found or if there is an error processing tidal data.
    """
    try:
        tidal_data = create_tidal_data(station, startdate, range_hrs, time_step_s)
        results = tidal_data.load_tidal_data(city_data_file)
        return TidalResults(*results)
    except FileNotFoundError:
        raise ValueError(f"City data file not found: {city_data_file}")
    except ValueError as e:
        raise ValueError(f"Error processing tidal data: {e}")
    except Exception as e:
        raise ValueError(f"An unexpected error occurred: {e}")

@dataclass
class TidalResults:
    """
    A data class to store the results of tidal data processing.

    Attributes:
        flow_speeds (list): The array of flow speeds in meters per second.
        times (list): The array of time steps in seconds.
        mooring_distance (float): The mooring distance in meters.
        latitude (float): The latitude of the buoy in radians.
        longitude (float): The longitude of the buoy in radians.
        station_name (str): The name of the NOAA station.
        nearest_city (str): The name of the nearest city to the buoy.
        cable_length (float): The length of the electrical cable in meters.
    """
    flow_speeds: list
    times: list
    mooring_distance: float
    latitude: float
    longitude: float
    station_name: str
    nearest_city: str
    cable_length: float