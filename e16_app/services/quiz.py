# -*- coding: utf-8 -*-
"""
Quiz attempt and question-serving service for E16 LMS.
Handles attempt tracking, randomized question selection, and option shuffling.
"""
import random
from ..extensions import db
from ..models import Quiz, QuizAttempt, Question, Choice


class QuizService:
    @staticmethod
    def get_attempt_count(user_id: str, quiz_id: str) -> int:
        """Count the number of attempts a student has made on a specific quiz."""
        return db.session.query(QuizAttempt).filter_by(user_id=user_id, quiz_id=quiz_id).count()

    @staticmethod
    def prepare_shuffled_questions(quiz_id: str):
        """Fetch all questions for a quiz, shuffle order, apply limit, and shuffle choices."""
        quiz = db.session.get(Quiz, quiz_id)
        if not quiz:
            return []

        questions = db.session.query(Question).filter_by(quiz_id=quiz_id).all()
        
        # Always shuffle question order for every attempt
        random.shuffle(questions)
        
        # Handle random selection subset
        if quiz.random_question_count and quiz.random_question_count > 0:
            if quiz.random_question_count <= len(questions):
                questions = questions[:quiz.random_question_count]

        # Fetch and shuffle choices for each question
        for q in questions:
            choices = db.session.query(Choice).filter_by(question_id=q.id).all()
            random.shuffle(choices)
            q.choices = choices

        return questions
