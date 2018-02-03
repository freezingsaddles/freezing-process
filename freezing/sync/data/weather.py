import logging
from datetime import timedelta

from sqlalchemy import text

from freezing.model import meta, orm

from freezing.sync.utils.wktutils import parse_point_wkt
from freezing.sync.wx.sunrise import Sun
from freezing.sync.wx.wunder import api as wu_api

from freezing.sync.config import config

from freezing.sync.data import BaseSync


class WeatherSync(BaseSync):
    """
    Synchronize rides from data with the database.
    """

    name = 'sync-weather'
    description = 'Sync all ride weather'

    def sync_weather(self, clear:bool = False, limit: int = None, cache_only: bool = False):
        sess = meta.scoped_session()

        if clear:
            self.logger.info("Clearing all weather data!")
            sess.query(orm.RideWeather).delete()

        if limit:
            self.logger.info("Fetching weather for first {0} rides".format(limit))
        else:
            self.logger.info("Fetching weather for all rides")

        # Find rides that have geo, but no weather
        sess.query(orm.RideWeather)
        q = text("""
            select R.id from rides R
            join ride_geo G on G.ride_id = R.id
            left join ride_weather W on W.ride_id = R.id
            where W.ride_id is null
            and date(R.start_date) < CURDATE() -- Only include rides from yesterday 
            and time(R.start_date) != '00:00:00' -- Exclude bad entries.
            ;
            """)

        c = wu_api.Client(api_key=config.WUNDERGROUND_API_KEY,
                          cache_dir=config.WUNDERGROUND_CACHE_DIR,
                          pause=7.0,  # Max requests 10/minute for developer license
                          cache_only=cache_only)

        rows = meta.engine.execute(q).fetchall()  # @UndefinedVariable
        num_rides = len(rows)

        for i, r in enumerate(rows):

            if limit and i >= limit:
                logging.info("Limit ({0}) reached".format(limit))
                break

            ride = sess.query(orm.Ride).get(r['id'])
            self.logger.info("Processing ride: {0} ({1}/{2})".format(ride.id, i, num_rides))

            try:

                start_geo_wkt = meta.scoped_session().scalar(ride.geo.start_geo.wkt)
                point = parse_point_wkt(start_geo_wkt)
                lon = point.lon
                lat = point.lat
                # We are doing only lat/lon now instead of us_city, since us_city seems to resolve to regional weather stations
                # rather than the closest weather stations ...
                # hist = c.history(ride.start_date, us_city=ride.location, lat=lat, lon=lon)
                hist = c.history(ride.start_date, lat=lat, lon=lon)

                ride_start = ride.start_date.replace(tzinfo=hist.date.tzinfo)
                ride_end = ride_start + timedelta(seconds=ride.elapsed_time)

                # NOTE: if elapsed_time is significantly more than moving_time then we need to assume
                # that the rider wasn't actually riding for this entire time (and maybe just grab temps closest to start of
                # ride as opposed to averaging observations during ride.

                ride_observations = hist.find_observations_within(ride_start, ride_end)
                start_obs = hist.find_nearest_observation(ride_start)
                end_obs = hist.find_nearest_observation(ride_end)

                def avg(l):
                    no_nulls = [e for e in l if e is not None]
                    if not no_nulls:
                        return None
                    return sum(no_nulls) / len(no_nulls) * 1.0  # to force float

                rw = orm.RideWeather()
                rw.ride_id = ride.id
                rw.ride_temp_start = start_obs.temp
                rw.ride_temp_end = end_obs.temp
                if len(ride_observations) <= 2:
                    # if we dont' have many observations, bookend the list with the start/end observations
                    ride_observations = [start_obs] + ride_observations + [end_obs]

                rw.ride_temp_avg = avg([o.temp for o in ride_observations])

                rw.ride_windchill_start = start_obs.windchill
                rw.ride_windchill_end = end_obs.windchill
                rw.ride_windchill_avg = avg([o.windchill for o in ride_observations])

                rw.ride_precip = sum([o.precip for o in ride_observations if o.precip is not None])
                rw.ride_rain = any([o.rain for o in ride_observations])
                rw.ride_snow = any([o.snow for o in ride_observations])

                rw.day_temp_min = hist.min_temp
                rw.day_temp_max = hist.max_temp

                # ride.weather_fetched = True  # (We don't have such an attribute, actually.)
                # (We get this from the activity now.)
                # ride.timezone = hist.date.tzinfo.zone

                sess.add(rw)
                sess.flush()

                if lat and lon:
                    try:
                        sun = Sun(lat=lat, lon=lon)
                        rw.sunrise = sun.sunrise(ride_start)
                        rw.sunset = sun.sunset(ride_start)
                    except:
                        self.logger.exception("Error getting sunrise/sunset for ride {0}".format(ride))
                        # But soldier on ...

            except:
                self.logger.exception("Error getting weather data for ride: {0}".format(ride))
                sess.rollback()

            else:
                sess.commit()
