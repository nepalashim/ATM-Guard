from backend.database import SessionLocal
from backend.models.db import Alert

db = SessionLocal()

# Count total alerts
total = db.query(Alert).count()
print(f"Total alerts in database: {total}")

# Get recent alerts
alerts = db.query(Alert).order_by(Alert.timestamp.desc()).limit(10).all()
print(f"\nLatest 10 alerts:")
print("-" * 80)

for alert in alerts:
    print(f"ID: {alert.id}")
    print(f"  Type: {alert.alert_type}")
    print(f"  Level: {alert.level}")
    print(f"  Object: {alert.object_detected}")
    print(f"  Confidence: {alert.confidence:.2%}" if alert.confidence else "  Confidence: N/A")
    print(f"  Camera: {alert.cam_id}")
    print(f"  Timestamp: {alert.timestamp}")
    print(f"  Detection Source: {alert.detection_source}")
    print(f"  Acknowledged: {alert.acknowledged}")
    print()

# Count by alert type
print("\nAlert Breakdown:")
print("-" * 80)
tool_alerts = db.query(Alert).filter(Alert.alert_type == "TOOL_DETECTED").count()
loiter_alerts = db.query(Alert).filter(Alert.alert_type == "LOITERING").count()
high_alerts = db.query(Alert).filter(Alert.level == "HIGH").count()
low_alerts = db.query(Alert).filter(Alert.level == "LOW").count()

print(f"TOOL_DETECTED alerts: {tool_alerts}")
print(f"LOITERING alerts: {loiter_alerts}")
print(f"HIGH threat alerts: {high_alerts}")
print(f"LOW threat alerts: {low_alerts}")
