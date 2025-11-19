from flask import Flask, render_template
import fastf1 as ff1 #fastf1 использует pandas dataframes
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import os
import numpy as np
from datetime import datetime

ff1.Cache.enable_cache("cache")
app = Flask(__name__)

if not os.path.exists("static/images"):
    os.makedirs("static/images")


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


def get_current_form(driver_count=10):
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


def generate_expert_prediction(next_race, track_history, current_form):
    if next_race is None or not track_history:
        return "Ожидаем начало сезона - собираем данные для прогноза"
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
            predictions.append(f"{best_team} традиционно сильны на этой трассе")
    
    # текущая форма
    if current_form:
        predictions.append(f"{current_form[0]["driver"]} в лучшей форме")
    
    if not predictions:
        predictions.append("")
    
    return ".".join(predictions)


def create_track_performance_chart(track_name, top_drivers_count=6):
    try:
        current_year = datetime.now().year
        years = list(range(current_year - 4, current_year))
        track_rating = get_driver_track_rating(track_name, top_drivers_count)
        current_form = get_current_form(top_drivers_count)
        top_drivers = set()
        for driver in track_rating:
            top_drivers.add(driver["driver"])
        for driver in current_form[:4]:
            top_drivers.add(driver["driver"])
        for year in years[-2:]:
            try:
                schedule = ff1.get_event_schedule(year)
                track_events = schedule[schedule["EventName"].str.contains(track_name, case=False, na=False)]
                if not track_events.empty:
                    event = track_events.iloc[0]
                    session = ff1.get_session(year, event.EventName, "R")
                    session.load()
                    podium_drivers = session.results["Abbreviation"].head(3).tolist()
                    for driver in podium_drivers:
                        top_drivers.add(driver)
            except:
                continue
        top_drivers = list(top_drivers)[:10]
        driver_data = []
        for driver in top_drivers:
            positions = []
            for year in years:
                try:
                    schedule = ff1.get_event_schedule(year)
                    track_events = schedule[schedule["EventName"].str.contains(track_name, case=False, na=False)]
                    if not track_events.empty:
                        event = track_events.iloc[0]
                        session = ff1.get_session(year, event.EventName, "R")
                        session.load()
                        driver_result = session.results[session.results["Abbreviation"] == driver]
                        if not driver_result.empty:
                            position = driver_result.iloc[0]["Position"]
                            positions.append(position)
                        else:
                            positions.append(None)
                    else:
                        positions.append(None)
                except Exception as e:
                    positions.append(None) 
            valid_positions = [p for p in positions if p is not None]
            avg_position = np.mean(valid_positions) if valid_positions else None
            
            driver_data.append({
                "driver": driver,
                "avg_position": avg_position,
                "positions": positions,
                "years": years
            })
        
        driver_data = [d for d in driver_data if d["avg_position"] is not None]
        driver_data.sort(key=lambda x: x["avg_position"])
        
        plt.figure(figsize=(14, 8))
        
        drivers = [d["driver"] for d in driver_data]
        avg_positions = [d["avg_position"] for d in driver_data]
        
        bars = plt.bar(drivers, avg_positions)
        
        for i, (bar, driver) in enumerate(zip(bars, drivers)): # красивая штука, zip объединяет в (bars, drivers) и потом enumerate проставляет индексы
            was_podium = False
            for data in driver_data:
                if data["driver"] == driver:
                    recent_positions = [p for p in data["positions"][-2:] if p is not None]
                    if any(pos <= 3 for pos in recent_positions):
                        was_podium = True
                        break
            if was_podium:
                bar.set_edgecolor("gold")
                bar.set_linewidth(3)
        
        plt.title(f"Средние позиции на трассе {track_name} (золотая рамка = был в топ-3 за последние 2 года)", fontsize=14, fontweight="bold")
        plt.xlabel("Гонщик", fontsize=12)
        plt.ylabel("Средняя позиция", fontsize=12)

        plt.gca().invert_yaxis()
        plt.ylim(20, 0)
        
        plt.grid(True, alpha=0.3, axis="y")
        plt.tight_layout()
        
        plt.savefig("static/images/track_performance.png", bbox_inches="tight", edgecolor="none")
        plt.close()
        return True
        
    except Exception as e:
        print(f"Ошибка создания графика производительности на трассе: {e}")
        return False


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


def create_pitstop_analysis(year, event):
    try:
        session = ff1.get_session(year, event, "R")
        session.load()
        laps = session.laps
        
        plt.figure(figsize=(14, 6))
        
        results = session.results
        top_drivers = results["Abbreviation"].head(8).tolist()
        podium_drivers = results["Abbreviation"].head(3).tolist()
        
        all_drivers = list(set(top_drivers + podium_drivers))[:10]
        
        for i, driver in enumerate(all_drivers):
            driver_laps = laps[laps["Driver"] == driver]
            pit_laps = driver_laps[driver_laps["PitInTime"].notna()]
            
            if not pit_laps.empty:
                finish_pos = results[results["Abbreviation"] == driver]["Position"].iloc[0]
                
                marker_style = "D" if driver in podium_drivers else "o"
                marker_size = 150 if driver in podium_drivers else 120
                
                plt.scatter(pit_laps["LapNumber"], [driver] * len(pit_laps), 
                           label=f"{driver} (P{finish_pos}){"*" if finish_pos <= 3 else ""}", 
                           s=marker_size, alpha=0.8, edgecolors="black", linewidth=1,
                           marker=marker_style)
        
        plt.title(f"Стратегии пит-стопов - {event} {year} (* = подиум, ромбы = призеры)", fontsize=14, fontweight="bold", pad=20)
        plt.xlabel("Номер круга", fontsize=12)
        plt.ylabel("Гонщик", fontsize=12)
        plt.legend(bbox_to_anchor=(1.05, 1), loc="upper left")
        plt.grid(True, alpha=0.3)
        
        max_lap = laps["LapNumber"].max()
        for lap in range(10, int(max_lap), 10):
            plt.axvline(x=lap, color="gray", linestyle="--", alpha=0.2)
        
        plt.tight_layout()
        plt.savefig("static/images/pitstop_analysis.png", bbox_inches="tight", dpi=100)
        plt.close()
        return True
    except Exception as e:
        print(f"Ошибка создания графика пит-стопов: {e}")
        return False


def create_lap_times_analysis(year, event):
    try:
        session = ff1.get_session(year, event, "R")
        session.load()
        laps = session.laps
        
        plt.figure(figsize=(12, 8))
        
        results = session.results
        top_drivers = results["Abbreviation"].head(6).tolist()
        podium_drivers = results["Abbreviation"].head(3).tolist()
        
        all_drivers = list(set(top_drivers + podium_drivers))[:8]
        
        for i, driver in enumerate(all_drivers):
            driver_laps = laps.pick_driver(driver)
            if not driver_laps.empty:
                finish_pos = results[results["Abbreviation"] == driver]["Position"].iloc[0]

                line_width = 3 if driver in podium_drivers else 1.5
                line_style = "-" if driver in podium_drivers else "-"

                plt.plot(driver_laps["LapNumber"], driver_laps["LapTime"], "o-", label=f"{driver} (P{finish_pos}){"*" if finish_pos <= 3 else ""}", markersize=2, linewidth=line_width, alpha=0.8, linestyle=line_style)
        
        plt.title(f"Сравнение времени кругов - {event} {year} (* = подиум, толстые линии = призеры)", fontsize=14, fontweight="bold")
        plt.xlabel("Номер круга", fontsize=12)
        plt.ylabel("Время круга", fontsize=12)
        plt.legend(bbox_to_anchor=(1.05, 1), loc="upper left")
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        
        plt.savefig("static/images/laptimes_analysis.png", bbox_inches="tight", dpi=100)
        plt.close()
        return True
    except Exception as e:
        print(f"Ошибка создания графика времени кругов: {e}")
        return False

###

@app.route("/")
def index():
    last_race, next_race = get_last_and_next_race()

    prediction_data = create_prediction_blocks(next_race)
    
    analysis_success = False
    laptimes_success = False
    track_performance_success = False
    
    if last_race is not None and hasattr(last_race, "year") and hasattr(last_race, "EventName"):
        analysis_success = create_pitstop_analysis(last_race.year, last_race.EventName)
        laptimes_success = create_lap_times_analysis(last_race.year, last_race.EventName)
        
        last_race_date = last_race.EventDate.strftime("%d.%m.%Y") if hasattr(last_race.EventDate, "strftime") else str(last_race.EventDate)
        last_race_name = last_race.EventName
    else:
        last_race_date = "Нет данных"
        last_race_name = "Сезон не начался"
    
    if next_race is not None and hasattr(next_race, "EventDate") and hasattr(next_race, "EventName"):
        next_race_date = next_race.EventDate.strftime("%d.%m.%Y") if hasattr(next_race.EventDate, "strftime") else str(next_race.EventDate)
        next_race_name = next_race.EventName
        
        track_performance_success = create_track_performance_chart(next_race_name)
    else:
        next_race_date = "Неизвестно"
        next_race_name = "Сезон завершен"
    
    return render_template("index.html",
                         last_race_name=last_race_name,
                         last_race_date=last_race_date,
                         next_race_name=next_race_name,
                         next_race_date=next_race_date,
                         analysis_success=analysis_success,
                         laptimes_success=laptimes_success,
                         track_performance_success=track_performance_success,
                         **prediction_data)

if __name__ == "__main__":
    app.run(debug=True)