from flask import Flask, render_template, jsonify, request
import fastf1 as ff1 #fastf1 использует pandas dataframes
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import os
from datetime import datetime

from plotting import create_gear_shifts_plot, create_pitstop_analysis, create_lap_time_plot, create_lap_times_analysis, create_position_changes_plot, create_speed_trace_plot, create_speed_visual_plot, create_track_map_plot, create_track_performance_chart
from analysis_utils import (
    get_available_seasons, 
    get_events_for_season, 
    get_drivers_for_session,
    get_session_types,
    get_last_and_next_race,
    get_driver_track_rating,
    get_current_form,
    get_session_results
)

if not os.path.exists("cache"):
    os.makedirs("cache")

ff1.Cache.enable_cache("cache")
app = Flask(__name__)


def get_track_history(track_name, years_back=5): # получение истории трека гонщиков
    try:
        current_year = datetime.now().year
        history = []

        for year in range(current_year - years_back, current_year):
            try:
                schedule = ff1.get_event_schedule(year)
                track_events = schedule[schedule["EventName"].str.contains(track_name, case=False, na=False)]
                if not track_events.empty:
                    event = track_events.iloc[0]
                    session = ff1.get_session(year, event.EventName, "R")
                    session.load()
                    winner = session.results.iloc[0]
                    history.append({
                        "year": year,
                        "winner": winner["FullName"],
                        "team": winner["TeamName"],
                        "points": winner["Points"]
                    })
            except Exception as e:
                print(f"Ошибка ff1 загрузки данных за {year}: {e}")
                continue
        return history
    
    except Exception as e:
        print(f"Ошибка ff1 получения истории трассы: {e}")
        return []


def generate_expert_prediction(next_race, track_history, current_form): # сам прогноз
    if next_race is None or not track_history:
        return ""
    track_name = next_race.EventName if hasattr(next_race, "EventName") else "предстоящей гонки"
    
    # анализ истории
    recent_winners = [h["winner"] for h in track_history[-2:]] if track_history else []
    dominant_teams = {}
    for h in track_history:
        team = h["team"]
        dominant_teams[team] = dominant_teams.get(team, 0) + 1
    
    # анализ формы
    top_drivers = [f["driver"] for f in current_form[:3]] if current_form else []
    
    # прогноз
    predictions = []
    
    # если есть повторяющийся победитель
    if len(recent_winners) >= 2 and recent_winners[0] == recent_winners[1]:
        predictions.append(f"{recent_winners[0]} имеет хорошую историю на этой трассе")
    
    # самые успешные команды
    if dominant_teams:
        best_team = max(dominant_teams, key=dominant_teams.get)
        if dominant_teams[best_team] >= 2:
            predictions.append(f"{best_team} сильны на этой трассе")
    
    # текущая форма
    if current_form:
        predictions.append(f"{current_form[0]["driver"]} в лучшей форме")
    
    if not predictions:
        predictions.append("")
    
    return ".".join(predictions)


def create_prediction_blocks(next_race):
    if next_race is None or (hasattr(next_race, "empty") and next_race.empty):
        return {
            "track_history": [],
            "current_form": [], 
            "track_rating": [],
            "expert_prediction": "Ожидаем начало сезона",
            "next_track_name": "Следующая гонка"
        }
    
    track_name = next_race.EventName if hasattr(next_race, "EventName") else "Следующая гонка"
    track_history = get_track_history(track_name)
    current_form = get_current_form()
    track_rating = get_driver_track_rating(track_name)
    expert_prediction = generate_expert_prediction(next_race, track_history, current_form)
    
    return {
        "track_history": track_history,
        "current_form": current_form,
        "track_rating": track_rating,
        "expert_prediction": expert_prediction,
        "next_track_name": track_name
    }


@app.route('/analysis') # страница анализа сессий
def analysis_page():
    seasons = get_available_seasons()
    current_year = 2025 
    events = get_events_for_season(current_year)
    session_types = get_session_types()
    
    return render_template('analysis.html', 
                         seasons=seasons, 
                         events=events,
                         session_types=session_types,
                         current_year=current_year)


@app.route('/api/events/<int:year>') # получение событий для сезона
def get_events_html(year):
    events = get_events_for_season(year)
    return jsonify({'events': events})


@app.route('/get_drivers_list', methods=['POST']) # получение гонщиков для сессии
def get_drivers_list():
    data = request.json
    year = int(data.get('year'))
    event = data.get('event')
    session_type = data.get('session')
    drivers = get_drivers_for_session(year, event, session_type)

    return render_template('partials/checkboxes.html', drivers=drivers)


@app.route('/perform_analysis', methods=['POST']) # выполнение анализа сессии
def perform_analysis():
    year = int(request.form.get('year'))
    event = request.form.get('event')
    session = request.form.get('session')
    
    selected_drivers = request.form.getlist('drivers')

    plot_data = create_lap_time_plot(year, event, session, selected_drivers)
    track_map = create_track_map_plot(year, event, session)
    session_results = get_session_results(year, event, session)
    gear_shifts = create_gear_shifts_plot(year, event, session)
    speed_map = create_speed_visual_plot(year, event, session)
    speed_trace = create_speed_trace_plot(year, event, session, selected_drivers)
    pos_changes = create_position_changes_plot(year, event, session)
    
    return render_template('analysis_result.html', 
                         plot_data=plot_data,
                         year=year,
                         event=event,
                         drivers=selected_drivers,
                         track_map=track_map,
                         session_results=session_results,
                         gear_shifts=gear_shifts,
                         speed_map=speed_map,
                         speed_trace=speed_trace,
                         pos_changes=pos_changes)


@app.route("/") # главная страница
def index():
    last_race, next_race = get_last_and_next_race()

    last_race_name = ""
    last_track_rating = []
    last_race_results = []
    next_track_rating = []
    current_form_data = get_current_form()

    if last_race is not None:
        last_race_name = last_race.EventName

        last_track_rating = get_driver_track_rating(last_race_name, top_count=5)

        all_res = get_session_results(last_race.year, last_race_name, 'R')
        last_race_results = all_res[:5] if all_res else []

    next_race_name = "Сезон завершен"
    if next_race is not None:
        next_race_name = next_race.EventName

        next_track_rating = get_driver_track_rating(next_race_name)
    
    pitstop_img = None
    laptimes_img = None
    track_img = None

    if last_race is not None and hasattr(last_race, "year"):
        pitstop_img = create_pitstop_analysis(last_race.year, last_race.EventName)
        laptimes_img = create_lap_times_analysis(last_race.year, last_race.EventName)
        
        last_race_date = last_race.EventDate.strftime("%d.%m.%Y") if hasattr(last_race.EventDate, "strftime") else str(last_race.EventDate)
        last_race_name = last_race.EventName
    else:
        last_race_date = "Нет данных"
        last_race_name = "Сезон не начался"
    
    if next_race is not None:
        next_race_date = next_race.EventDate.strftime("%d.%m.%Y") if hasattr(next_race.EventDate, "strftime") else str(next_race.EventDate)
        next_race_name = next_race.EventName
        
        track_img = create_track_performance_chart(next_race_name)
    else:
        next_race_date = "Неизвестно"
        next_race_name = "Сезон завершен"

    current_time = datetime.now().strftime("%d.%m.%Y %H:%M")
    
    return render_template("index.html",
                         last_race_name=last_race_name,
                         last_race_date=last_race_date,
                         last_track_rating=last_track_rating,
                         last_race_results=last_race_results,
                         next_race_name=next_race_name,
                         next_race_date=next_race_date,
                         track_rating=next_track_rating,
                         pitstop_img=pitstop_img,
                         laptimes_img=laptimes_img,
                         track_img=track_img,
                         current_time=current_time,
                         current_form=current_form_data)

if __name__ == "__main__":
    app.run()