import json
import os
from datetime import datetime, timedelta

class GamificationManager:
    def __init__(self, data_file='user_stats.json'):
        self.data_file = data_file
        self.stats = self.load_stats()
        
    def load_stats(self):
        """Load or initialize user statistics"""
        if os.path.exists(self.data_file):
            with open(self.data_file, 'r') as f:
                return json.load(f)
        return {
            'total_sessions': 0,
            'total_minutes': 0,
            'longest_session': 0,
            'current_streak': 0,
            'longest_streak': 0,
            'last_session_date': None,
            'achievements': [],
            'session_history': []
        }
    
    def save_stats(self):
        """Persist statistics to JSON"""
        with open(self.data_file, 'w') as f:
            json.dump(self.stats, f, indent=2)
    
    def record_session(self, duration_minutes, avg_focus, peak_focus):
        """Record a completed session"""
        today = datetime.now().strftime('%Y-%m-%d')
        
        # Update totals
        self.stats['total_sessions'] += 1
        self.stats['total_minutes'] += duration_minutes
        if duration_minutes > self.stats['longest_session']:
            self.stats['longest_session'] = duration_minutes
        
        # Update streak
        last_date = self.stats['last_session_date']
        if last_date:
            last = datetime.strptime(last_date, '%Y-%m-%d')
            diff = (datetime.now() - last).days
            if diff == 1:
                self.stats['current_streak'] += 1
            elif diff > 1:
                self.stats['current_streak'] = 1
        else:
            self.stats['current_streak'] = 1
        
        if self.stats['current_streak'] > self.stats['longest_streak']:
            self.stats['longest_streak'] = self.stats['current_streak']
        
        self.stats['last_session_date'] = today
        
        # Log session
        self.stats['session_history'].append({
            'date': datetime.now().isoformat(),
            'duration': duration_minutes,
            'avg_focus': avg_focus,
            'peak_focus': peak_focus
        })
        
        # Check achievements
        new_achievements = self.check_achievements(duration_minutes, avg_focus, peak_focus)
        
        self.save_stats()
        return new_achievements
    
    def check_achievements(self, duration, avg_focus, peak_focus):
        """Check if any achievements were unlocked"""
        achievements = []
        unlocked = set(self.stats['achievements'])
        
        # First Session
        if 'first_session' not in unlocked and self.stats['total_sessions'] == 1:
            achievements.append({'id': 'first_session', 'name': 'First Steps', 'desc': 'Complete your first session'})
        
        # 10 Sessions
        if 'sessions_10' not in unlocked and self.stats['total_sessions'] >= 10:
            achievements.append({'id': 'sessions_10', 'name': 'Dedicated', 'desc': 'Complete 10 sessions'})
        
        # 30 Minute Session
        if 'long_session' not in unlocked and duration >= 30:
            achievements.append({'id': 'long_session', 'name': 'Endurance', 'desc': 'Complete a 30-minute session'})
        
        # 7-Day Streak
        if 'streak_7' not in unlocked and self.stats['current_streak'] >= 7:
            achievements.append({'id': 'streak_7', 'name': 'Week Warrior', 'desc': '7-day streak achieved'})
        
        # Peak Flow (90%+ for session)
        if 'peak_flow' not in unlocked and peak_focus >= 0.9:
            achievements.append({'id': 'peak_flow', 'name': 'Flow Master', 'desc': 'Reach 90% focus'})
        
        # Add to unlocked list
        for ach in achievements:
            self.stats['achievements'].append(ach['id'])
        
        return achievements
    
    def get_stats(self):
        """Return current statistics"""
        return {
            'total_sessions': self.stats['total_sessions'],
            'total_minutes': self.stats['total_minutes'],
            'longest_session': self.stats['longest_session'],
            'current_streak': self.stats['current_streak'],
            'longest_streak': self.stats['longest_streak'],
            'achievements': len(self.stats['achievements']),
            'recent_achievements': self.stats['achievements'][-3:] if self.stats['achievements'] else []
        }

    def get_history(self):
        """Return session history for analytics"""
        return self.stats['session_history']

# Global instance
gamification = GamificationManager()
