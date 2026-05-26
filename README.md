# ATM-Guard
Built a full-stack AI surveillance platform for ATM/security environments that monitors live RTSP camera feeds, detects suspicious human presence, identifies dangerous tools, and generates real-time alerts for supervisors and managers.  The system uses computer vision models for human detection, loitering detection, and tool detection. 
Built a full-stack AI surveillance platform for ATM/security environments that monitors live RTSP camera feeds, detects suspicious human presence, identifies dangerous tools, and generates real-time alerts for supervisors and managers.

The system uses computer vision models for human detection, loitering detection, and tool detection. A YOLO-based pipeline detects people for LOW loitering alerts and a fine-tuned YOLO tool detector identifies high-risk objects such as hammer, drill, wrench, screwdriver, and pliers for HIGH threat alerts. The platform includes live camera streaming, alert history, snapshot capture, 5-second video clip recording, alert acknowledgement, supervisor comments, manager escalation, SOS handling, role-based access, and PDF reporting.

Technology Stack Used
Frontend:
React, TypeScript, Vite, Tailwind CSS, Recharts, Axios, WebSocket

Backend:
FastAPI, Python, SQLAlchemy, PostgreSQL, Pydantic, Uvicorn

Computer Vision / AI:
YOLO11, Ultralytics, OpenCV, PyTorch, ByteTrack tracking, fine-tuned custom YOLO model for tool detection

Real-Time Features:
RTSP camera streaming, MJPEG live feed, WebSocket alert broadcasting, real-time dashboard updates

Storage & Reporting:
PostgreSQL database, local snapshot/video clip storage, PDF report generation

Security & Access:
JWT authentication, role-based access for Supervisor and Manager, protected API route
