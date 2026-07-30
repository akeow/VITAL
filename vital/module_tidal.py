"""
module_tidal.py

Load and process tidal resource data from NOAA or local fallback files.

Functions:
    create_tidal_data(...): Create a TidalData instance.
    process_tidal_data(...): Load tidal data using NOAA first, then local fallback if provided.

Classes:
    TidalData: Loads tidal data and related site metadata.
    TidalResults: Container for processed tidal data.
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
    Load and process tidal data from NOAA or local fallback files.
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
            req_data = self.session.get(url, verify=False, timeout=30)
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
            req_data = self.session.get(url, verify=False, timeout=30)
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
            req_data = self.session.get(url, verify=False, timeout=30)
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
            req_data = self.session.get(url, verify=False, timeout=30)
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
        if 'current_predictions' not in input_data or 'cp' not in input_data['current_predictions']:
            raise ValueError("Unexpected NOAA tidal data format.")

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
    
    def get_nearest_city_from_coords(self, buoylat: float, buoylon: float, citytextfile: str) -> tuple:
        """
        Computes nearest city and cable length from a buoy location.
        """
        datafile = pd.read_csv(citytextfile, skipinitialspace=True)

        required_cols = {"Name", "Latitude", "Longitude"}
        missing_cols = required_cols - set(datafile.columns)
        if missing_cols:
            raise ValueError(
                f"City data file must contain columns {required_cols}. "
                f"Missing columns: {missing_cols}"
            )

        d_cable_len = np.zeros(len(datafile))
        for ind in datafile.index:
            city_lat = math.radians(float(datafile.loc[ind, "Latitude"]))
            city_lon = math.radians(float(datafile.loc[ind, "Longitude"]))
            d_cable_len[ind] = self.distance(buoylat, city_lat, buoylon, city_lon)

        idx = np.argmin(d_cable_len)
        closest_city = datafile.loc[idx, "Name"]
        cable_len_m = round(d_cable_len[idx], 2)

        return closest_city, cable_len_m

    def load_tidal_data(self, city_data_file: str) -> tuple:
        """
        Loads tidal data and calculates the necessary attributes from NOAA.

        Args:
            city_data_file (str): The path to the text file containing city data,
                including latitude, longitude, and city names.

        Returns:
            tuple: A tuple containing:
                flow_speeds (np.ndarray): Flow speeds in meters per second.
                times (np.ndarray): Time steps in seconds.
                mooring_distance (float): Mooring distance in meters.
                latitude (float): Latitude of the buoy in radians.
                longitude (float): Longitude of the buoy in radians.
                station_name (str): NOAA station name.
                nearest_city (str): Nearest city to the buoy.
                cable_length (float): Electrical cable length in meters.

        Raises:
            ValueError: If the city data file is not found or NOAA tidal data cannot be processed.
        """
        self.station_name = self.get_station_name()
        if self.station_name is None:
            raise ValueError(f"Unable to retrieve station name for station '{self.station}'.")

        # Basic station metadata
        if self.station.lower().startswith("pct"):
            input_data = self.get_station_info()
            if not input_data or "stations" not in input_data or not input_data["stations"]:
                raise ValueError(f"Unable to retrieve station info for station '{self.station}'.")

            self.buoy_latitude_rad = math.radians(float(input_data["stations"][0]["lat"]))
            self.buoy_longitude_rad = math.radians(float(input_data["stations"][0]["lng"]))
            self.mooring_distance_m = DEFAULT_MOORING_DISTANCE_M
        else:
            input_data = self.get_deployment_info()
            if not input_data:
                raise ValueError(f"Unable to retrieve deployment info for station '{self.station}'.")

            # Gracefully handle missing depth
            if "depth" in input_data and input_data["depth"] is not None:
                self.mooring_distance_m = float(input_data["depth"])
                if input_data.get("units") == "feet":
                    self.mooring_distance_m *= CONVERT.ft2m
            else:
                self.mooring_distance_m = DEFAULT_MOORING_DISTANCE_M

            if "deployments" not in input_data or not input_data["deployments"]:
                raise ValueError(f"Deployment coordinates are missing for station '{self.station}'.")

            self.buoy_latitude_rad = math.radians(float(input_data["deployments"][0]["lat"]))
            self.buoy_longitude_rad = math.radians(float(input_data["deployments"][0]["lng"]))

        # Retrieve tidal predictions
        tidal_data = self.get_tidal_data()
        if not tidal_data:
            raise ValueError(f"Unable to retrieve tidal data for station '{self.station}'.")

        tidal_speed_cms = self.extract_tidal_speed(tidal_data)
        tidal_time_s = np.array(self.extract_tidal_time(tidal_data))
        tidal_speed_ms = np.array([float(x) for x in tidal_speed_cms]) * CONVERT.cms2ms

        if len(tidal_time_s) < 2 or len(tidal_speed_ms) < 2:
            raise ValueError(f"Not enough tidal data points retrieved for station '{self.station}'.")

        tidal_CubicSpline = PchipInterpolator(tidal_time_s - tidal_time_s[0], tidal_speed_ms)
        end_time = self.range_hrs * 3600.0
        self.time_s = np.arange(0, end_time, self.time_step_s)
        self.flow_speeds_m_s = tidal_CubicSpline(self.time_s)

        self.flow_speeds_m_s = np.abs(self.flow_speeds_m_s)
        self.flow_speeds_m_s = np.maximum(self.flow_speeds_m_s, MIN_FLOW_SPEED)

        try:
            self.nearest_city, self.electrical_cable_length_m = self.get_nearest_city_from_coords(
                self.buoy_latitude_rad,
                self.buoy_longitude_rad,
                city_data_file
            )
        except Exception:
            self.nearest_city = "Unknown"
            self.electrical_cable_length_m = 0.0

        return (
            self.flow_speeds_m_s,
            self.time_s,
            self.mooring_distance_m,
            self.buoy_latitude_rad,
            self.buoy_longitude_rad,
            self.station_name,
            self.nearest_city,
            self.electrical_cable_length_m,
            "NOAA",
        )
    
    def load_local_tidal_data(self, local_file: str, fallback_metadata: dict, city_data_file: str = None) -> tuple:
        """
        Loads tidal data from a local file and applies fallback metadata.

        The local file must contain at least two whitespace-delimited columns:
        ``t`` for time in seconds and ``U`` for flow speed in m/s.

        Args:
            local_file (str): Path to a local tidal data file.
            fallback_metadata (dict): Fallback site metadata. Required keys are
                ``station_name``, ``latitude_deg``, ``longitude_deg``, and
                ``mooring_distance_m``. Optional keys are ``nearest_city`` and
                ``cable_length_m``.
            city_data_file (str, optional): Optional city metadata file used to
                estimate nearest city and cable length.

        Returns:
            tuple: Processed tidal data and metadata, including flow speeds,
            time values, mooring distance, location, station name, nearest city,
            cable length, and source label.
        """
        if fallback_metadata is None:
            raise ValueError("fallback_metadata must be provided for local tidal data.")

        # Read local tidal file
        df = pd.read_csv(local_file, sep=r"\s+", engine="python")

        # Validate required columns
        required_cols = {"t", "U"}
        missing_cols = required_cols - set(df.columns)
        if missing_cols:
            raise ValueError(
                f"Local tidal file must contain columns {required_cols}. "
                f"Missing columns: {missing_cols}"
            )

        # Validate fallback metadata
        required_meta = [
            "station_name", 
            "latitude_deg",
            "longitude_deg",
            "mooring_distance_m", 
        ]
        
        missing_meta = [k for k in required_meta if k not in fallback_metadata]
        if missing_meta:
            raise ValueError(
                "fallback_metadata is missing required keys: "
                f"{missing_meta}"
            )

        # Store local data
        self.time_s = df["t"].to_numpy(dtype=float)
        self.flow_speeds_m_s = df["U"].to_numpy(dtype=float)

        # Ensure nonnegative flow speeds and apply minimum flow floor
        self.flow_speeds_m_s = np.abs(self.flow_speeds_m_s)
        self.flow_speeds_m_s = np.maximum(self.flow_speeds_m_s, MIN_FLOW_SPEED)

        # Apply fallback metadata
        self.station_name = fallback_metadata["station_name"]
        self.buoy_latitude_rad = math.radians(float(fallback_metadata["latitude_deg"]))
        self.buoy_longitude_rad = math.radians(float(fallback_metadata["longitude_deg"]))
        self.mooring_distance_m = float(fallback_metadata["mooring_distance_m"])

        # Default label if nothing better is available
        self.nearest_city = fallback_metadata.get("nearest_city", "Unknown")
        self.electrical_cable_length_m = float(fallback_metadata.get("cable_length_m", 0.0))

        # Try to compute nearest city automatically if city data is available
        if city_data_file is not None:
            try:
                computed_city, computed_cable = self.get_nearest_city_from_coords(
                    self.buoy_latitude_rad,
                    self.buoy_longitude_rad,
                    city_data_file
                )
                self.nearest_city = computed_city
                self.electrical_cable_length_m = computed_cable
            except Exception:
                pass

        return (
            self.flow_speeds_m_s,
            self.time_s,
            self.mooring_distance_m,
            self.buoy_latitude_rad,
            self.buoy_longitude_rad,
            self.station_name,
            self.nearest_city,
            self.electrical_cable_length_m,
            "local_file",
        )
    
    

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
    range_hrs: int = 2 * 7 * 24,
    time_step_s: int = 3600,
    city_data_file: str = "../data/AlaskaCityLatLong.txt",
    local_file: str = None,
    fallback_metadata: dict = None
) -> tuple:
    """
    Processes tidal data in one step.

    This function first attempts to load NOAA tidal data. If that fails and a
    local fallback file is provided, it loads the local file instead.
    """
    tidal_data = create_tidal_data(station, startdate, range_hrs, time_step_s)

    try:
        results = tidal_data.load_tidal_data(city_data_file)
        return TidalResults(*results)

    except Exception as noaa_error:
        if local_file is not None and fallback_metadata is not None:
            try:
                results = tidal_data.load_local_tidal_data(local_file, fallback_metadata, city_data_file)
                return TidalResults(*results)
            except Exception as local_error:
                raise ValueError(
                    f"NOAA data failed ({noaa_error}) and local fallback also failed ({local_error})."
                ) from local_error

        raise ValueError(f"Error processing tidal data: {noaa_error}") from noaa_error

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
        source (str): Data source used to create the results ("NOAA" or "local_file").
    """
    flow_speeds: list
    times: list
    mooring_distance: float
    latitude: float
    longitude: float
    station_name: str
    nearest_city: str
    cable_length: float
    source: str


