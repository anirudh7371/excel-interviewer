# monitoring.py - Comprehensive monitoring and testing utilities

import asyncio
import aiohttp
import time
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any
import psutil
import redis
from sqlalchemy import create_engine, text
from dataclasses import dataclass
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('monitoring.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

@dataclass
class HealthCheckResult:
    service: str
    status: str
    response_time: float
    details: Dict[str, Any]
    timestamp: datetime

@dataclass
class PerformanceMetrics:
    cpu_usage: float
    memory_usage: float
    disk_usage: float
    active_sessions: int
    questions_answered_today: int
    average_response_time: float
    error_rate: float

class SystemMonitor:
    """Comprehensive system monitoring"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.redis_client = redis.from_url(config.get('redis_url', 'redis://localhost:6379'))
        self.db_engine = create_engine(config.get('database_url'))
        
    async def health_check_api(self) -> HealthCheckResult:
        """Check API health endpoint"""
        start_time = time.time()
        api_url = self.config.get('api_url', 'http://localhost:8000')
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{api_url}/api/health", timeout=10) as response:
                    response_time = time.time() - start_time
                    
                    if response.status == 200:
                        data = await response.json()
                        return HealthCheckResult(
                            service="api",
                            status="healthy",
                            response_time=response_time,
                            details=data,
                            timestamp=datetime.now()
                        )
                    else:
                        return HealthCheckResult(
                            service="api",
                            status="unhealthy",
                            response_time=response_time,
                            details={"status_code": response.status},
                            timestamp=datetime.now()
                        )
                        
        except Exception as e:
            return HealthCheckResult(
                service="api",
                status="down",
                response_time=time.time() - start_time,
                details={"error": str(e)},
                timestamp=datetime.now()
            )
    
    def health_check_database(self) -> HealthCheckResult:
        """Check database connectivity and performance"""
        start_time = time.time()
        
        try:
            with self.db_engine.connect() as conn:
                # Test basic connectivity
                result = conn.execute(text("SELECT 1")).fetchone()
                
                # Test table access
                result = conn.execute(text("SELECT COUNT(*) FROM questions")).fetchone()
                question_count = result[0]
                
                # Test recent sessions
                result = conn.execute(text("""
                    SELECT COUNT(*) FROM interview_sessions 
                    WHERE started_at > NOW() - INTERVAL '1 day'
                """)).fetchone()
                recent_sessions = result[0]
                
                response_time = time.time() - start_time
                
                return HealthCheckResult(
                    service="database",
                    status="healthy",
                    response_time=response_time,
                    details={
                        "question_count": question_count,
                        "recent_sessions": recent_sessions
                    },
                    timestamp=datetime.now()
                )
                
        except Exception as e:
            return HealthCheckResult(
                service="database",
                status="down",
                response_time=time.time() - start_time,
                details={"error": str(e)},
                timestamp=datetime.now()
            )
    
    def health_check_redis(self) -> HealthCheckResult:
        """Check Redis connectivity and performance"""
        start_time = time.time()
        
        try:
            # Test basic connectivity
            self.redis_client.ping()
            
            # Test read/write
            test_key = f"health_check_{datetime.now().timestamp()}"
            self.redis_client.set(test_key, "test_value", ex=60)
            retrieved = self.redis_client.get(test_key)
            self.redis_client.delete(test_key)
            
            # Get memory usage
            info = self.redis_client.info()
            memory_usage = info.get('used_memory_human', 'unknown')
            connected_clients = info.get('connected_clients', 0)
            
            response_time = time.time() - start_time
            
            return HealthCheckResult(
                service="redis",
                status="healthy",
                response_time=response_time,
                details={
                    "memory_usage": memory_usage,
                    "connected_clients": connected_clients,
                    "read_write_test": "passed" if retrieved else "failed"
                },
                timestamp=datetime.now()
            )
            
        except Exception as e:
            return HealthCheckResult(
                service="redis",
                status="down",
                response_time=time.time() - start_time,
                details={"error": str(e)},
                timestamp=datetime.now()
            )
    
    def get_system_metrics(self) -> PerformanceMetrics:
        """Get comprehensive system performance metrics"""
        
        # System resources
        cpu_usage = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        # Application metrics from database
        try:
            with self.db_engine.connect() as conn:
                # Active sessions in last hour
                result = conn.execute(text("""
                    SELECT COUNT(*) FROM interview_sessions 
                    WHERE started_at > NOW() - INTERVAL '1 hour'
                    AND status = 'in_progress'
                """)).fetchone()
                active_sessions = result[0]
                
                # Questions answered today
                result = conn.execute(text("""
                    SELECT COUNT(*) FROM answers 
                    WHERE created_at > CURRENT_DATE
                """)).fetchone()
                questions_today = result[0]
                
                # Average response time (approximated from time_spent)
                result = conn.execute(text("""
                    SELECT AVG(time_spent) FROM answers 
                    WHERE created_at > NOW() - INTERVAL '1 hour'
                """)).fetchone()
                avg_response_time = float(result[0]) if result[0] else 0
                
        except Exception as e:
            logger.error(f"Failed to get database metrics: {e}")
            active_sessions = 0
            questions_today = 0
            avg_response_time = 0
        
        # Calculate error rate (simplified)
        try:
            # Count low-scoring answers as potential errors
            with self.db_engine.connect() as conn:
                result = conn.execute(text("""
                    SELECT 
                        COUNT(CASE WHEN score < 20 THEN 1 END) as errors,
                        COUNT(*) as total
                    FROM answers 
                    WHERE created_at > NOW() - INTERVAL '1 hour'
                """)).fetchone()
                
                if result and result[1] > 0:
                    error_rate = (float(result[0]) / float(result[1])) * 100
                else:
                    error_rate = 0
                    
        except Exception:
            error_rate = 0
        
        return PerformanceMetrics(
            cpu_usage=cpu_usage,
            memory_usage=memory.percent,
            disk_usage=disk.percent,
            active_sessions=active_sessions,
            questions_answered_today=questions_today,
            average_response_time=avg_response_time,
            error_rate=error_rate
        )
    
    async def full_health_check(self) -> Dict[str, HealthCheckResult]:
        """Run comprehensive health check on all services"""
        
        results = {}
        
        # API health check
        results['api'] = await self.health_check_api()
        
        # Database health check
        results['database'] = self.health_check_database()
        
        # Redis health check  
        results['redis'] = self.health_check_redis()
        
        return results

class AlertManager:
    """Handle alerts and notifications"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.smtp_config = config.get('smtp', {})
        self.alert_thresholds = config.get('alert_thresholds', {
            'cpu_usage': 80,
            'memory_usage': 85,
            'disk_usage': 90,
            'response_time': 5.0,
            'error_rate': 10.0
        })
    
    def should_alert(self, metrics: PerformanceMetrics) -> List[str]:
        """Check if any metrics exceed alert thresholds"""
        alerts = []
        
        if metrics.cpu_usage > self.alert_thresholds['cpu_usage']:
            alerts.append(f"High CPU usage: {metrics.cpu_usage:.1f}%")
        
        if metrics.memory_usage > self.alert_thresholds['memory_usage']:
            alerts.append(f"High memory usage: {metrics.memory_usage:.1f}%")
        
        if metrics.disk_usage > self.alert_thresholds['disk_usage']:
            alerts.append(f"High disk usage: {metrics.disk_usage:.1f}%")
        
        if metrics.average_response_time > self.alert_thresholds['response_time']:
            alerts.append(f"Slow response time: {metrics.average_response_time:.1f}s")
        
        if metrics.error_rate > self.alert_thresholds['error_rate']:
            alerts.append(f"High error rate: {metrics.error_rate:.1f}%")
        
        return alerts
    
    def send_email_alert(self, subject: str, body: str):
        """Send email alert"""
        if not self.smtp_config.get('enabled', False):
            logger.info(f"Email alerts disabled. Would send: {subject}")
            return
        
        try:
            msg = MIMEMultipart()
            msg['From'] = self.smtp_config['from']
            msg['To'] = ', '.join(self.smtp_config['to'])
            msg['Subject'] = f"[Excel Interviewer Alert] {subject}"
            
            msg.attach(MIMEText(body, 'plain'))
            
            server = smtplib.SMTP(self.smtp_config['host'], self.smtp_config['port'])
            if self.smtp_config.get('use_tls'):
                server.starttls()
            if self.smtp_config.get('username'):
                server.login(self.smtp_config['username'], self.smtp_config['password'])
            
            server.send_message(msg)
            server.quit()
            
            logger.info(f"Alert sent: {subject}")
            
        except Exception as e:
            logger.error(f"Failed to send email alert: {e}")

class LoadTester:
    """Load testing utilities"""
    
    def __init__(self, api_url: str):
        self.api_url = api_url
    
    async def test_session_creation(self, concurrent_users: int = 10) -> Dict[str, Any]:
        """Test concurrent session creation"""
        
        async def create_session():
            async with aiohttp.ClientSession() as session:
                start_time = time.time()
                try:
                    async with session.post(f"{self.api_url}/api/sessions/", 
                                          json={
                                              "candidate_name": "Test User",
                                              "candidate_email": "test@example.com", 
                                              "role_level": "intermediate"
                                          }) as response:
                        response_time = time.time() - start_time
                        return {
                            "success": response.status == 200,
                            "response_time": response_time,
                            "status_code": response.status
                        }
                except Exception as e:
                    return {
                        "success": False,
                        "response_time": time.time() - start_time,
                        "error": str(e)
                    }
        
        # Run concurrent requests
        tasks = [create_session() for _ in range(concurrent_users)]
        results = await asyncio.gather(*tasks)
        
        # Analyze results
        successful = sum(1 for r in results if r["success"])
        total_time = sum(r["response_time"] for r in results)
        avg_response_time = total_time / len(results)
        max_response_time = max(r["response_time"] for r in results)
        
        return {
            "concurrent_users": concurrent_users,
            "successful_requests": successful,
            "success_rate": (successful / len(results)) * 100,
            "average_response_time": avg_response_time,
            "max_response_time": max_response_time,
            "total_time": total_time
        }
    
    async def test_question_retrieval(self, sessions: int = 5, questions_per_session: int = 3):
        """Test question retrieval performance"""
        
        session_ids = []
        
        # Create test sessions
        async with aiohttp.ClientSession() as client:
            for _ in range(sessions):
                async with client.post(f"{self.api_url}/api/sessions/",
                                     json={
                                         "candidate_name": "Load Test",
                                         "role_level": "intermediate"
                                     }) as response:
                    if response.status == 200:
                        data = await response.json()
                        session_ids.append(data["session_id"])
        
        # Test question retrieval
        async def get_questions(session_id):
            async with aiohttp.ClientSession() as client:
                times = []
                for _ in range(questions_per_session):
                    start_time = time.time()
                    async with client.get(f"{self.api_url}/api/sessions/{session_id}/question") as response:
                        response_time = time.time() - start_time
                        times.append(response_time)
                return times
        
        tasks = [get_questions(sid) for sid in session_ids]
        results = await asyncio.gather(*tasks)
        
        # Flatten results
        all_times = [time for session_times in results for time in session_times]
        
        return {
            "sessions_tested": len(session_ids),
            "questions_per_session": questions_per_session,
            "total_requests": len(all_times),
            "average_response_time": sum(all_times) / len(all_times),
            "max_response_time": max(all_times),
            "min_response_time": min(all_times)
        }

class IntegrationTester:
    """End-to-end integration testing"""
    
    def __init__(self, api_url: str, db_engine, redis_client):
        self.api_url = api_url
        self.db_engine = db_engine
        self.redis_client = redis_client
    
    async def test_complete_interview_flow(self) -> Dict[str, Any]:
        """Test a complete interview from start to finish"""
        
        test_results = {
            "steps_completed": 0,
            "total_steps": 6,
            "errors": [],
            "performance": {}
        }
        
        session_id = None
        
        try:
            async with aiohttp.ClientSession() as client:
                
                # Step 1: Create session
                start_time = time.time()
                async with client.post(f"{self.api_url}/api/sessions/", 
                                     json={
                                         "candidate_name": "Integration Test",
                                         "candidate_email": "test@example.com",
                                         "role_level": "intermediate"
                                     }) as response:
                    
                    if response.status != 200:
                        test_results["errors"].append(f"Session creation failed: {response.status}")
                        return test_results
                    
                    data = await response.json()
                    session_id = data["session_id"]
                    test_results["performance"]["session_creation"] = time.time() - start_time
                    test_results["steps_completed"] += 1
                
                # Step 2: Get first question
                start_time = time.time()
                async with client.get(f"{self.api_url}/api/sessions/{session_id}/question") as response:
                    
                    if response.status != 200:
                        test_results["errors"].append(f"Question retrieval failed: {response.status}")
                        return test_results
                    
                    question_data = await response.json()
                    test_results["performance"]["question_retrieval"] = time.time() - start_time
                    test_results["steps_completed"] += 1
                
                # Step 3: Submit answer
                start_time = time.time()
                async with client.post(f"{self.api_url}/api/sessions/{session_id}/answer",
                                     json={
                                         "session_id": session_id,
                                         "question_id": question_data["question_id"],
                                         "user_answer": "=SUM(A1:A10)",
                                         "time_spent": 30.5
                                     }) as response:
                    
                    if response.status != 200:
                        test_results["errors"].append(f"Answer submission failed: {response.status}")
                        return test_results
                    
                    answer_result = await response.json()
                    test_results["performance"]["answer_submission"] = time.time() - start_time
                    test_results["steps_completed"] += 1
                
                # Step 4: Test chat functionality
                start_time = time.time()
                async with client.post(f"{self.api_url}/api/sessions/{session_id}/chat",
                                     json={
                                         "message": "Can you give me a hint?",
                                         "session_id": session_id
                                     }) as response:
                    
                    if response.status != 200:
                        test_results["errors"].append(f"Chat functionality failed: {response.status}")
                        return test_results
                    
                    test_results["performance"]["chat_response"] = time.time() - start_time
                    test_results["steps_completed"] += 1
                
                # Step 5: Get session report  
                start_time = time.time()
                async with client.get(f"{self.api_url}/api/sessions/{session_id}/report") as response:
                    
                    if response.status != 200:
                        test_results["errors"].append(f"Report generation failed: {response.status}")
                        return test_results
                    
                    report_data = await response.json()
                    test_results["performance"]["report_generation"] = time.time() - start_time
                    test_results["steps_completed"] += 1
                
                # Step 6: Verify database consistency
                start_time = time.time()
                with self.db_engine.connect() as conn:
                    # Check session exists
                    result = conn.execute(text(
                        "SELECT COUNT(*) FROM interview_sessions WHERE id = :session_id"
                    ), {"session_id": session_id}).fetchone()
                    
                    if result[0] == 0:
                        test_results["errors"].append("Session not found in database")
                        return test_results
                    
                    # Check answer was recorded
                    result = conn.execute(text(
                        "SELECT COUNT(*) FROM answers WHERE session_id = :session_id"
                    ), {"session_id": session_id}).fetchone()
                    
                    if result[0] == 0:
                        test_results["errors"].append("Answer not found in database")
                        return test_results
                
                test_results["performance"]["database_verification"] = time.time() - start_time
                test_results["steps_completed"] += 1
                
        except Exception as e:
            test_results["errors"].append(f"Unexpected error: {str(e)}")
        
        return test_results
    
    async def test_concurrent_interviews(self, num_concurrent: int = 5) -> Dict[str, Any]:
        """Test multiple concurrent interview sessions"""
        
        async def run_interview():
            try:
                result = await self.test_complete_interview_flow()
                return {
                    "success": result["steps_completed"] == result["total_steps"],
                    "steps_completed": result["steps_completed"],
                    "errors": result["errors"],
                    "total_time": sum(result["performance"].values())
                }
            except Exception as e:
                return {
                    "success": False,
                    "steps_completed": 0,
                    "errors": [str(e)],
                    "total_time": 0
                }
        
        # Run concurrent interviews
        tasks = [run_interview() for _ in range(num_concurrent)]
        results = await asyncio.gather(*tasks)
        
        # Analyze results
        successful = sum(1 for r in results if r["success"])
        total_errors = sum(len(r["errors"]) for r in results)
        avg_completion_time = sum(r["total_time"] for r in results) / len(results)
        
        return {
            "concurrent_interviews": num_concurrent,
            "successful_interviews": successful,
            "success_rate": (successful / num_concurrent) * 100,
            "total_errors": total_errors,
            "average_completion_time": avg_completion_time,
            "individual_results": results
        }

class MonitoringDashboard:
    """Generate monitoring dashboard data"""
    
    def __init__(self, monitor: SystemMonitor):
        self.monitor = monitor
    
    async def generate_dashboard_data(self) -> Dict[str, Any]:
        """Generate comprehensive dashboard data"""
        
        # Get current metrics
        metrics = self.monitor.get_system_metrics()
        health_results = await self.monitor.full_health_check()
        
        # Get historical data (last 24 hours)
        historical_data = self.get_historical_metrics()
        
        # System status summary
        all_services_healthy = all(
            result.status == "healthy" for result in health_results.values()
        )
        
        dashboard_data = {
            "timestamp": datetime.now().isoformat(),
            "overall_status": "healthy" if all_services_healthy else "degraded",
            "current_metrics": {
                "cpu_usage": metrics.cpu_usage,
                "memory_usage": metrics.memory_usage,
                "disk_usage": metrics.disk_usage,
                "active_sessions": metrics.active_sessions,
                "questions_answered_today": metrics.questions_answered_today,
                "average_response_time": metrics.average_response_time,
                "error_rate": metrics.error_rate
            },
            "service_health": {
                service: {
                    "status": result.status,
                    "response_time": result.response_time,
                    "details": result.details
                }
                for service, result in health_results.items()
            },
            "historical_metrics": historical_data,
            "alerts": self.get_active_alerts(metrics)
        }
        
        return dashboard_data
    
    def get_historical_metrics(self) -> Dict[str, List]:
        """Get historical performance metrics"""
        # In a real implementation, this would query a time-series database
        # For now, return sample data structure
        
        hours = []
        cpu_data = []
        memory_data = []
        sessions_data = []
        
        # Generate last 24 hours of sample data
        now = datetime.now()
        for i in range(24):
            hour = now - timedelta(hours=i)
            hours.append(hour.strftime("%H:00"))
            
            # Sample data - in production, query actual metrics
            cpu_data.append(45 + (i % 5) * 8)  # Sample CPU usage
            memory_data.append(60 + (i % 3) * 10)  # Sample memory usage  
            sessions_data.append(max(0, 20 - (i % 8) * 3))  # Sample sessions
        
        return {
            "hours": list(reversed(hours)),
            "cpu_usage": list(reversed(cpu_data)),
            "memory_usage": list(reversed(memory_data)),
            "active_sessions": list(reversed(sessions_data))
        }
    
    def get_active_alerts(self, metrics: PerformanceMetrics) -> List[Dict[str, Any]]:
        """Get current active alerts"""
        
        alert_manager = AlertManager({})  # Use default config
        alert_messages = alert_manager.should_alert(metrics)
        
        alerts = []
        for message in alert_messages:
            severity = "critical" if "High" in message else "warning"
            alerts.append({
                "message": message,
                "severity": severity,
                "timestamp": datetime.now().isoformat()
            })
        
        return alerts

# Main monitoring script
async def run_monitoring_cycle(config: Dict[str, Any]):
    """Run a complete monitoring cycle"""
    
    monitor = SystemMonitor(config)
    alert_manager = AlertManager(config)
    dashboard = MonitoringDashboard(monitor)
    
    logger.info("Starting monitoring cycle")
    
    try:
        # Generate dashboard data
        dashboard_data = await dashboard.generate_dashboard_data()
        
        # Log current status
        logger.info(f"System status: {dashboard_data['overall_status']}")
        logger.info(f"Active sessions: {dashboard_data['current_metrics']['active_sessions']}")
        logger.info(f"Questions answered today: {dashboard_data['current_metrics']['questions_answered_today']}")
        
        # Check for alerts
        metrics = PerformanceMetrics(**dashboard_data['current_metrics'])
        alerts = alert_manager.should_alert(metrics)
        
        if alerts:
            alert_body = f"""
Excel Interviewer System Alert

The following issues have been detected:

{chr(10).join(f"• {alert}" for alert in alerts)}

Current System Metrics:
• CPU Usage: {metrics.cpu_usage:.1f}%
• Memory Usage: {metrics.memory_usage:.1f}%  
• Disk Usage: {metrics.disk_usage:.1f}%
• Active Sessions: {metrics.active_sessions}
• Error Rate: {metrics.error_rate:.1f}%

Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
            
            alert_manager.send_email_alert("System Performance Alert", alert_body)
        
        # Save dashboard data to file for external consumption
        with open('monitoring_dashboard.json', 'w') as f:
            json.dump(dashboard_data, f, indent=2)
        
        logger.info("Monitoring cycle completed successfully")
        
    except Exception as e:
        logger.error(f"Monitoring cycle failed: {e}")
        alert_manager.send_email_alert(
            "Monitoring System Failure", 
            f"The monitoring system encountered an error: {str(e)}"
        )

# CLI interface
async def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Excel Interviewer Monitoring & Testing')
    parser.add_argument('command', choices=['monitor', 'test', 'load-test', 'integration-test'])
    parser.add_argument('--api-url', default='http://localhost:8000', help='API base URL')
    parser.add_argument('--database-url', default='postgresql://postgres:password@localhost/excel_interviewer')
    parser.add_argument('--redis-url', default='redis://localhost:6379')
    parser.add_argument('--concurrent-users', type=int, default=10, help='Concurrent users for load testing')
    
    args = parser.parse_args()
    
    config = {
        'api_url': args.api_url,
        'database_url': args.database_url,
        'redis_url': args.redis_url,
        'alert_thresholds': {
            'cpu_usage': 80,
            'memory_usage': 85,
            'disk_usage': 90,
            'response_time': 5.0,
            'error_rate': 10.0
        },
        'smtp': {
            'enabled': False  # Configure as needed
        }
    }
    
    if args.command == 'monitor':
        await run_monitoring_cycle(config)
    
    elif args.command == 'test':
        monitor = SystemMonitor(config)
        health_results = await monitor.full_health_check()
        
        print("\n🏥 Health Check Results:")
        print("=" * 50)
        
        for service, result in health_results.items():
            status_emoji = "✅" if result.status == "healthy" else "❌"
            print(f"{status_emoji} {service.upper()}: {result.status}")
            print(f"   Response Time: {result.response_time:.3f}s")
            
            if result.details:
                for key, value in result.details.items():
                    print(f"   {key}: {value}")
            print()
    
    elif args.command == 'load-test':
        load_tester = LoadTester(args.api_url)
        
        print(f"\n🔄 Running load test with {args.concurrent_users} concurrent users...")
        
        # Test session creation
        session_results = await load_tester.test_session_creation(args.concurrent_users)
        
        print(f"\n📊 Session Creation Load Test Results:")
        print(f"   Concurrent Users: {session_results['concurrent_users']}")
        print(f"   Success Rate: {session_results['success_rate']:.1f}%")
        print(f"   Average Response Time: {session_results['average_response_time']:.3f}s")
        print(f"   Max Response Time: {session_results['max_response_time']:.3f}s")
        
        # Test question retrieval
        question_results = await load_tester.test_question_retrieval(5, 3)
        
        print(f"\n📋 Question Retrieval Load Test Results:")
        print(f"   Sessions Tested: {question_results['sessions_tested']}")
        print(f"   Total Requests: {question_results['total_requests']}")
        print(f"   Average Response Time: {question_results['average_response_time']:.3f}s")
        print(f"   Min/Max Response Time: {question_results['min_response_time']:.3f}s / {question_results['max_response_time']:.3f}s")
    
    elif args.command == 'integration-test':
        from sqlalchemy import create_engine
        import redis
        
        db_engine = create_engine(args.database_url)
        redis_client = redis.from_url(args.redis_url)
        
        integration_tester = IntegrationTester(args.api_url, db_engine, redis_client)
        
        print("\n🧪 Running integration tests...")
        
        # Single interview test
        single_result = await integration_tester.test_complete_interview_flow()
        
        print(f"\n📝 Single Interview Test:")
        print(f"   Steps Completed: {single_result['steps_completed']}/{single_result['total_steps']}")
        
        if single_result['errors']:
            print(f"   Errors: {len(single_result['errors'])}")
            for error in single_result['errors']:
                print(f"     • {error}")
        else:
            print("   ✅ All steps completed successfully")
        
        if single_result['performance']:
            print(f"   Performance Summary:")
            for step, time_taken in single_result['performance'].items():
                print(f"     {step}: {time_taken:.3f}s")
        
        # Concurrent interview test
        print(f"\n👥 Running concurrent interview test with 3 sessions...")
        concurrent_result = await integration_tester.test_concurrent_interviews(3)
        
        print(f"   Success Rate: {concurrent_result['success_rate']:.1f}%")
        print(f"   Average Completion Time: {concurrent_result['average_completion_time']:.3f}s")
        print(f"   Total Errors: {concurrent_result['total_errors']}")

if __name__ == "__main__":
    asyncio.run(main())