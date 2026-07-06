from typing import Optional, Dict, Any


def render_arrival_message(place_name: Optional[str], template: Optional[str], ctx: Dict[str, Any]) -> str:
    """渲染到院訊息。支援 {place_name}/{name}、{distance_km}、{eta_min}、{provider}、{speed}。
    距離四捨五入到1位小數，eta為整數。
    """
    name = (place_name or "診所").strip()
    distance_km = float(ctx.get("distance_km", 0.0))
    eta_min = int(ctx.get("eta_min", 0))
    provider = str(ctx.get("provider", "本地直線"))
    speed = ctx.get("speed")

    # 速度註記（本地模式時常用）
    speed_note = ""
    if speed is not None:
        speed_note = f"（平均 {speed} km/h）"

    if template and template.strip():
        s = template
        s = s.replace("{place_name}", name).replace("{name}", name)
        s = s.replace("{distance_km}", f"{distance_km:.1f}")
        s = s.replace("{eta_min}", str(eta_min))
        s = s.replace("{provider}", provider)
        s = s.replace("{speed}", str(speed) if speed is not None else "")
        return s

    # 預設模板：一律帶名稱（未命名預設「診所」，不特殊對待 — 用戶指示；
    # 想要客製文案的群可用 message_template）
    return (
        f"🚗 注意：來程車輛接近「{name}」\n"
        f"距離：{distance_km:.1f} 公里，約 {eta_min} 分鐘（{provider}）{speed_note}"
    )
