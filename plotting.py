import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
from matplotlib import colormaps
import numpy as np
import fastf1 as ff1
import fastf1.plotting
import io
import base64
from datetime import datetime
from analysis_utils import get_driver_track_rating, get_current_form

fastf1.plotting.setup_mpl(mpl_timedelta_support=True)
try:
    ff1.Cache.enable_cache("cache")
except:
    pass

def get_image_base64(): # превращает текущий график matplotlib в строку для html
    img = io.BytesIO()
    plt.savefig(img, format='png', bbox_inches='tight')
    img.seek(0)
    return base64.b64encode(img.getvalue()).decode('utf-8') # кодирую байты в строку base64


def create_pitstop_analysis(year, event): # график анализа пит-стопов
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
        image_data = get_image_base64()
        plt.close() # очищаем память
        return image_data
    
    except Exception as e:
        print(f"Ошибка создания графика пит-стопов: {e}")
        return False


def create_track_performance_chart(track_name, top_drivers_count=6): # график производительности гонщиков на трассе
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
        
        image_data = get_image_base64()
        plt.close()
        return image_data
        
    except Exception as e:
        print(f"Ошибка создания графика производительности на трассе: {e}")
        return False
    

def create_lap_times_analysis(year, event): # график анализа времени кругов
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
        
        image_data = get_image_base64()
        plt.close()
        return image_data
    
    except Exception as e:
        print(f"Ошибка создания графика времени кругов: {e}")
        return False


### Страница результатов анализа, perform_analysis ###

def create_lap_time_plot(year, event_name, session_type, selected_drivers): # график времени круга
    try:
        session = ff1.get_session(year, event_name, session_type)
        session.load()
        
        plt.figure(figsize=(10, 6))
        
        for driver in selected_drivers:
            laps = session.laps.pick_driver(driver)
            if not laps.empty:
                clean_laps = laps.pick_quicklaps()
                plt.plot(clean_laps['LapNumber'], clean_laps['LapTime'], label=driver)
        
        plt.title(f"Анализ темпа: {event_name} {year}")
        plt.xlabel("Круг")
        plt.ylabel("Время")
        plt.legend()
        plt.grid(True, alpha=0.3)
        
        image_data = get_image_base64()
        plt.close()
        return image_data
        
    except Exception as e:
        print(f"Ошибка построения графика: {e}")
        plt.close()
        return None
    
    
def rotate(xy, *, angle):
    rot_mat = np.array([[np.cos(angle), np.sin(angle)],
                        [-np.sin(angle), np.cos(angle)]])
    return np.matmul(xy, rot_mat)


def create_track_map_plot(year, event_name, session_type): # карта трассы с поворотами
    try:
        session = ff1.get_session(year, event_name, session_type)
        session.load(laps=True, telemetry=True)
        
        lap = session.laps.pick_fastest()
        pos = lap.get_pos_data()
        circuit_info = session.get_circuit_info()

        track = pos.loc[:, ('X', 'Y')].to_numpy()
        track_angle = circuit_info.rotation / 180 * np.pi
        rotated_track = rotate(track, angle=track_angle)

        plt.figure(figsize=(10, 6))
        plt.plot(rotated_track[:, 0], rotated_track[:, 1], color='black', lw=3)

        plt.title(f"Карта трассы: {session.event['Location']} ({year})", fontsize=15)
        plt.axis('equal')
        plt.xticks([])
        plt.yticks([])
        
        return get_image_base64()
    except Exception as e:
        print(f"Ошибка при создании карты трассы: {e}")
        return None
    

def create_gear_shifts_plot(year, event_name, session_type): # график переключения передач
    try:
        session = ff1.get_session(year, event_name, session_type)
        session.load(laps=True, telemetry=True)
        
        lap = session.laps.pick_fastest()
        tel = lap.get_telemetry()
        circuit_info = session.get_circuit_info()

        x = np.array(tel['X'].values)
        y = np.array(tel['Y'].values)
        points = np.array([x, y]).T
        
        track_angle = circuit_info.rotation / 180 * np.pi
        rotated_points = rotate(points, angle=track_angle)
        
        points_reshaped = rotated_points.reshape(-1, 1, 2)
        segments = np.concatenate([points_reshaped[:-1], points_reshaped[1:]], axis=1)
        gear = tel['nGear'].to_numpy().astype(float)

        cmap = colormaps['Paired']
        lc_comp = LineCollection(segments, norm=plt.Normalize(1, cmap.N+1), cmap=cmap)
        lc_comp.set_array(gear)
        lc_comp.set_linewidth(5)

        plt.figure(figsize=(10, 6))
        plt.gca().add_collection(lc_comp)
        plt.axis('equal')
        plt.tick_params(labelleft=False, left=False, labelbottom=False, bottom=False)
        
        plt.title(f"Переключение передач: {lap['Driver']} - {event_name} {year}", fontsize=15)

        cbar = plt.colorbar(mappable=lc_comp, label="Передача", boundaries=np.arange(1, 10))
        cbar.set_ticks(np.arange(1.5, 9.5))
        cbar.set_ticklabels(np.arange(1, 9))
        
        return get_image_base64()
    except Exception as e:
        print(f"Ошибка создания графика передач: {e}")
        return None
    

def create_speed_visual_plot(year, event_name, session_type): # визуализация скорости на трассе
    try:
        session = ff1.get_session(year, event_name, session_type)
        session.load(laps=True, telemetry=True)
        
        lap = session.laps.pick_fastest()
        tel = lap.get_telemetry()
        circuit_info = session.get_circuit_info()

        x = tel['X'].to_numpy()
        y = tel['Y'].to_numpy()
        points = np.array([x, y]).T
        
        track_angle = circuit_info.rotation / 180 * np.pi
        rotated_points = rotate(points, angle=track_angle)
        
        speed = tel['Speed'].to_numpy()
        
        rotated_points_reshaped = rotated_points.reshape(-1, 1, 2)
        segments = np.concatenate([rotated_points_reshaped[:-1], rotated_points_reshaped[1:]], axis=1)

        fig, ax = plt.subplots(figsize=(10, 6))
        plt.subplots_adjust(left=0.05, right=0.95, top=0.9, bottom=0.15)
        ax.axis('off')

        ax.plot(rotated_points[:, 0], rotated_points[:, 1], color='black', lw=14, zorder=0)

        norm = plt.Normalize(speed.min(), speed.max())
        lc = LineCollection(segments, cmap='plasma', norm=norm, lw=6, zorder=1)
        lc.set_array(speed)
        ax.add_collection(lc)
        ax.set_aspect('equal')

        plt.title(f"Визуализация скорости: {lap['Driver']} - {event_name} {year}", fontsize=15, pad=20)

        cbar_ax = fig.add_axes([0.25, 0.08, 0.5, 0.03])
        plt.colorbar(lc, cax=cbar_ax, orientation='horizontal', label='Скорость (км/ч)')
        
        return get_image_base64()
    except Exception as e:
        print(f"Ошибка создания графика скорости: {e}")
        return None
    

def create_speed_trace_plot(year, event_name, session_type, selected_drivers): # график скорости выбранных гонщиков
    try:
        if len(selected_drivers) < 2:
            return None

        session = ff1.get_session(year, event_name, session_type)
        session.load(laps=True, telemetry=True)
        
        plt.figure(figsize=(12, 5))
        
        drivers_to_compare = selected_drivers[:2]
        
        for driver_code in drivers_to_compare:
            lap = session.laps.pick_driver(driver_code).pick_fastest()
            tel = lap.get_car_data().add_distance()
            
            team_color = fastf1.plotting.get_team_color(lap['Team'], session=session)
            
            plt.plot(tel['Distance'], tel['Speed'], color=team_color, label=driver_code, linewidth=2)

        plt.xlabel('Дистанция (метры)')
        plt.ylabel('Скорость (км/ч)')
        plt.legend()
        plt.title(f"Сравнение скорости: {' vs '.join(drivers_to_compare)}\n{event_name} {year}")
        plt.grid(True, alpha=0.3)
        
        return get_image_base64()
    except Exception as e:
        print(f"Ошибка создания Speed Trace: {e}")
        return None
    

def create_position_changes_plot(year, event_name, session_type): # график изменения позиций
    try:
        session = ff1.get_session(year, event_name, session_type)
        session.load(telemetry=False, weather=False)
        
        fig, ax = plt.subplots(figsize=(10, 6))
        
        for drv in session.drivers:
            drv_laps = session.laps.pick_driver(drv)
            if drv_laps.empty:
                continue
                
            abb = drv_laps['Driver'].iloc[0]
            style = ff1.plotting.get_driver_style(identifier=abb,
                                                 style=['color', 'linestyle'],
                                                 session=session)

            ax.plot(drv_laps['LapNumber'], drv_laps['Position'],
                    label=abb, **style, alpha=0.8)

        ax.set_ylim([20.5, 0.5])
        ax.set_yticks([1, 5, 10, 15, 20])
        ax.set_xlabel('Круг')
        ax.set_ylabel('Позиция')
        
        plt.title(f"Изменение позиций в гонке: {event_name} {year}")
        ax.legend(bbox_to_anchor=(1.0, 1.02), loc='upper left', fontsize='small', ncol=1)
        plt.grid(True, alpha=0.2)
        plt.tight_layout()
        
        return get_image_base64()
    except Exception as e:
        print(f"Ошибка создания графика позиций: {e}")
        return None