from ..extensions import db
from ..models import Quiz, QuizAttempt, QuizAnswer, Question, Choice, Submission
from ..time_utils import utcnow

class GradingService:
    @staticmethod
    def grade_quiz_attempt(user_id, quiz_id, answers_data, served_q_ids=None):
        """
        Grades a quiz attempt and saves it to the database.
        answers_data: dict of {question_id: choice_id}
        """
        quiz = db.session.get(Quiz, quiz_id)
        if not quiz:
            return None
            
        if served_q_ids:
            questions = db.session.query(Question).filter(Question.quiz_id == quiz_id, Question.id.in_(served_q_ids)).all()
        else:
            questions = db.session.query(Question).filter_by(quiz_id=quiz_id).all()
        total_questions = len(questions)
        correct_count = 0
        
        attempt = QuizAttempt(user_id=user_id, quiz_id=quiz_id)
        db.session.add(attempt)
        db.session.flush() # Get attempt ID
        
        for q in questions:
            user_answer_list = answers_data.get(f"question_{q.id}", [])
            if not isinstance(user_answer_list, list):
                user_answer_list = [user_answer_list]
                
            user_answer_list = [val for val in user_answer_list if val is not None and str(val).strip() != ""]
            is_correct = False
            
            if q.q_type == 'mcq':
                user_choice_id = user_answer_list[0] if user_answer_list else None
                if user_choice_id:
                    correct_choice = db.session.query(Choice).filter_by(question_id=q.id, is_correct=True).first()
                    if correct_choice and str(correct_choice.id) == str(user_choice_id):
                        is_correct = True
                        
                    selected_choice = db.session.query(Choice).filter_by(id=user_choice_id, question_id=q.id).first()
                    if selected_choice:
                        db.session.add(QuizAnswer(attempt_id=attempt.id, question_id=q.id, choice_id=user_choice_id))
                    else:
                        db.session.add(QuizAnswer(attempt_id=attempt.id, question_id=q.id, choice_id=None))
                else:
                    db.session.add(QuizAnswer(attempt_id=attempt.id, question_id=q.id, choice_id=None))
                    
            elif q.q_type == 'checkbox':
                user_choice_ids = user_answer_list
                correct_choices = db.session.query(Choice).filter_by(question_id=q.id, is_correct=True).all()
                correct_choice_ids = [str(c.id) for c in correct_choices]
                
                if set(user_choice_ids) == set(correct_choice_ids) and len(user_choice_ids) > 0:
                    is_correct = True
                    
                if user_choice_ids:
                    inserted_any = False
                    for cid in user_choice_ids:
                        selected_choice = db.session.query(Choice).filter_by(id=cid, question_id=q.id).first()
                        if selected_choice:
                            db.session.add(QuizAnswer(attempt_id=attempt.id, question_id=q.id, choice_id=cid))
                            inserted_any = True
                    if not inserted_any:
                        db.session.add(QuizAnswer(attempt_id=attempt.id, question_id=q.id, choice_id=None))
                else:
                    db.session.add(QuizAnswer(attempt_id=attempt.id, question_id=q.id, choice_id=None))
                    
            elif q.q_type == 'fill_in_blank':
                user_text = user_answer_list[0] if user_answer_list else ""
                raw_user_text = user_text
                user_text = user_text.strip().lower()
                correct_choices = db.session.query(Choice).filter_by(question_id=q.id).all()
                
                for c in correct_choices:
                    if c.text.strip().lower() == user_text:
                        is_correct = True
                        break
                        
                db.session.add(QuizAnswer(attempt_id=attempt.id, question_id=q.id, choice_id=None, text_answer=raw_user_text))
                        
            if is_correct:
                correct_count += 1
        
        score = (correct_count / total_questions * 100) if total_questions > 0 else 0
        attempt.score = score
        attempt.passed = score >= quiz.pass_score
        attempt.completed_at = utcnow()
        db.session.commit()
        
        return attempt

    @staticmethod
    def grade_assignment_submission(submission_id, score, feedback, teacher_id):
        """
        Updates an assignment submission with a grade and feedback.
        """
        sub = db.session.get(Submission, submission_id)
        if not sub:
            return False
            
        sub.score = max(0, min(100, int(score)))
        sub.feedback = feedback
        sub.status = "graded"
        sub.graded_at = utcnow()
        sub.graded_by = teacher_id
        db.session.commit()
        return True
