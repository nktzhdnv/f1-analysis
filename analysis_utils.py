import fastf1 as ff1
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from datetime import datetime
import numpy as np
import pandas as pd


try:
    ff1.Cache.enable_cache("cache")
except:
    pass


def get_last_and_next_race(): # получение последей и следующей гонки
    current_year = datetime.now().year
    try:
        schedule = ff1.get_event_schedule(current_year)
        completed_races = schedule[schedule["EventDate"] < datetime.now()]
        if not completed_races.empty:
            last_race = completed_races.iloc[-1]
        else:
            last_year_schedule = ff1.get_event_schedule(current_year - 1)
            last_race = last_year_schedule.iloc[-1] if not last_year_schedule.empty else None
        
        upcoming_races = schedule[schedule["EventDate"] >= datetime.now()]
        if not upcoming_races.empty:
            next_race = upcoming_races.iloc[0]
        else:
            next_race = None
        return last_race, next_race
    
    except Exception as e:
        print(f"Ошибка ff1 получения расписания: {e}")
        return None, None


def get_available_seasons(): # список доступных сезонов
    current_year = datetime.now().year
    return list(range(2018, current_year + 1))


def get_events_for_season(year): # список событий для сезона
    try:
        schedule = ff1.get_event_schedule(year)
        events = []
        for _, event in schedule.iterrows():
            events.append({
                'round': int(event['RoundNumber']),
                'name': event['EventName'],
                'official_name': event['OfficialEventName'],
                'location': event['Location'],
                'country': event['Country'],
                'date': event['EventDate'].strftime('%d.%m.%Y'),
                'full_date': event['EventDate']
            })
        return events
    except Exception as e:
        print(f"Ошибка загрузки событий для {year}: {e}")
        return []


def get_drivers_for_session(year, event_name, session_type='R'): # список гонщиков для сессии
    try:
        session = ff1.get_session(year, event_name, session_type)
        session.load(laps=False, telemetry=False, weather=False)
        drivers = []
        
        if hasattr(session, 'results') and session.results is not None:
            for _, result in session.results.iterrows():
                drivers.append({
                    'abbreviation': result['Abbreviation'],
                    'name': result['FullName'],
                    'team': result['TeamName'],
                    'number': result['DriverNumber'],
                    'position': result['Position'] if 'Position' in result else 99
                })
        return sorted(drivers, key=lambda x: x.get('position', 99))
    except Exception as e:
        print(f"Ошибка загрузки гонщиков для {year} {event_name} {session_type}: {e}")
        return []

def get_session_types():
    return [
        {'value': 'R', 'name': 'Гонка (Race)'},
        {'value': 'Q', 'name': 'Квалификация'},
        {'value': 'S', 'name': 'Спринт'},
        {'value': 'FP1', 'name': 'Практика 1'},
        {'value': 'FP2', 'name': 'Практика 2'},
        {'value': 'FP3', 'name': 'Практика 3'}
    ]


def get_current_form(driver_count=10): # текущая форма гонщиков по последним гонкам
    try:
        current_year = datetime.now().year
        schedule = ff1.get_event_schedule(current_year)
        completed_races = schedule[schedule["EventDate"] < datetime.now()]
        if len(completed_races) < 2:
            return []
        
        recent_races = completed_races.tail(3)
        driver_points = {}
        
        for _, race in recent_races.iterrows():
            try:
                session = ff1.get_session(current_year, race.EventName, "R")
                session.load()
                for _, result in session.results.iterrows():
                    driver = result["Abbreviation"]
                    points = result["Points"]
                    if driver not in driver_points:
                        driver_points[driver] = []
                    driver_points[driver].append(points)
            except Exception as e:
                print(f"Ошибка ff1 загрузки гонки {race.EventName}: {e}")
                continue

        driver_avg_points = []
        for driver, points_list in driver_points.items():
            avg_points = np.mean(points_list)
            driver_avg_points.append({
                "driver": driver,
                "avg_points": round(avg_points, 1),
                "races": len(points_list)
            })
        driver_avg_points.sort(key=lambda x: x["avg_points"], reverse=True)
        return driver_avg_points[:driver_count]
    
    except Exception as e:
        print(f"Ошибка ff1 получения текущей формы: {e}")
        return []


def get_driver_track_rating(track_name, top_count=8): # рейтинг гонщиков на конкретной трассе по историческим данным
    try:
        current_year = datetime.now().year
        driver_stats = {}
        
        for year in range(current_year - 3, current_year):
            try:
                schedule = ff1.get_event_schedule(year)
                track_events = schedule[schedule["EventName"].str.contains(track_name, case=False, na=False)]
                if not track_events.empty:
                    event = track_events.iloc[0]
                    session = ff1.get_session(year, event.EventName, "R")
                    session.load()
                    for _, result in session.results.iterrows():
                        driver = result["Abbreviation"]
                        points = result["Points"]
                        position = result["Position"]
                        if driver not in driver_stats:
                            driver_stats[driver] = {
                                "total_points": 0,
                                "races_count": 0,
                                "best_position": 99,
                                "positions": []
                            }
                        driver_stats[driver]["total_points"] += points
                        driver_stats[driver]["races_count"] += 1
                        driver_stats[driver]["positions"].append(position)
                        driver_stats[driver]["best_position"] = min(driver_stats[driver]["best_position"], position)
                        
            except Exception as e:
                print(f"Ошибка анализа трассы {track_name} за {year}: {e}")
                continue

        driver_ratings = []
        for driver, stats in driver_stats.items():
            if stats["races_count"] >= 1:
                avg_points = stats["total_points"] / stats["races_count"]
                position_bonus = (20 - stats["best_position"]) * 0.5
                consistency_bonus = min(5, 10 / np.std(stats["positions"]) if len(stats["positions"]) > 1 else 0)

                rating = avg_points + position_bonus + consistency_bonus

                driver_ratings.append({
                    "driver": driver,
                    "rating": round(rating, 1),
                    "avg_points": round(avg_points, 1),
                    "races": stats["races_count"],
                    "best_pos": stats["best_position"]
                })
        return sorted(driver_ratings, key=lambda x: x["rating"], reverse=True)[:top_count]
        
    except Exception as e:
        print(f"Ошибка расчета рейтинга трассы: {e}")
        return []
    

def get_session_results(year, event_name, session_type='R'): # таблица результатов сессии
    try:
        session = ff1.get_session(year, event_name, session_type)
        session.load(laps=False, telemetry=False, weather=False)
        
        results_list = []
        if session.results is not None and not session.results.empty:
            for _, row in session.results.iterrows(): 
                status = row['Status']
                time_val = str(row['Time']).split('.')[-2] if pd.notna(row['Time']) else status
                
                results_list.append({
                    'position': int(row['Position']) if pd.notna(row['Position']) else 'NC',
                    'number': row['DriverNumber'],
                    'driver': row['Abbreviation'],
                    'team': row['TeamName'],
                    'points': row['Points'],
                    'status': status
                })
        return results_list
    except Exception as e:
        print(f"Ошибка получения результатов: {e}")
        return []
    

def get_last_race_winner(last_race_event): # получение победителя последней гонки
    try:
        session = ff1.get_session(last_race_event.year, last_race_event.EventName, 'R')
        session.load(laps=False, telemetry=False, weather=False)
        
        if not session.results.empty:
            winner = session.results.iloc[0]
            return {
                'name': winner['FullName'],
                'abb': winner['Abbreviation'],
                'team': winner['TeamName']
            }
        return None
    except Exception as e:
        print(f"Ошибка при получении победителя: {e}")
        return None