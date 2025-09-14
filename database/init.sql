-- Create database if not exists
SELECT 'CREATE DATABASE excel_interviewer' 
WHERE NOT EXISTS (
    SELECT FROM pg_database WHERE datname = 'excel_interviewer'
);

-- Connect to the database
\c excel_interviewer;

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create indexes and schema adjustments (no ENUMs since models use VARCHAR)

-- Seed initial question bank
INSERT INTO questions (
    category, difficulty, question_text, question_type, 
    canonical_answer, alternatives, explanation, hints, tags
) VALUES 

-- Beginner Questions
('Basic Formulas', 'beginner', 
 'You have sales data in cells A1:A10. Write a formula to calculate the total sales.', 
 'formula', '=SUM(A1:A10)', 
 '["=SUM(A:A)", "SUM(A1:A10)"]', 
 'SUM function adds all numbers in a range. A1:A10 specifies the range from A1 to A10.', 
 '["Think about which function adds numbers together", "The function starts with =SUM and needs a range", "Use A1:A10 to specify the range from A1 to A10"]',
 'sum,basic,formulas'),

('Basic Formulas', 'beginner', 
 'Calculate the average of values in cells B1 through B5.', 
 'formula', '=AVERAGE(B1:B5)', 
 '["=AVERAGE(B:B)", "AVERAGE(B1:B5)"]', 
 'AVERAGE function calculates the arithmetic mean of numbers in a range.', 
 '["Use a function that calculates the mean", "The function is AVERAGE with a range", "Specify the range B1:B5"]',
 'average,basic,statistics'),

('Basic Functions', 'beginner', 
 'Count how many cells contain numbers in the range C1:C20.', 
 'formula', '=COUNT(C1:C20)', 
 '["=COUNT(C:C)", "COUNT(C1:C20)"]', 
 'COUNT function counts cells containing numbers, ignoring text and blank cells.', 
 '["Think about counting numeric values only", "Use COUNT function", "Apply it to range C1:C20"]',
 'count,basic,data'),

-- Intermediate Questions
('Lookup Functions', 'intermediate', 
 'You have a product table (A1:C10) with Product ID, Product Name, and Price. Write a formula to find the price of product "P001".', 
 'formula', '=VLOOKUP("P001",A1:C10,3,FALSE)', 
 '["=INDEX(C1:C10,MATCH(\"P001\",A1:A10,0))", "=VLOOKUP(\"P001\",A:C,3,0)"]', 
 'VLOOKUP searches for P001 in the first column and returns the corresponding value from the 3rd column (price).', 
 '["Use a lookup function to find values in a table", "VLOOKUP needs: lookup value, table range, column number, exact match", "The syntax is =VLOOKUP(\"P001\",A1:C10,3,FALSE)"]',
 'vlookup,lookup,intermediate'),

('Conditional Logic', 'intermediate', 
 'Write a formula that shows "Pass" if a student''s score in cell D2 is 70 or above, otherwise "Fail".', 
 'formula', '=IF(D2>=70,"Pass","Fail")', 
 '["=IF(D2>69,\"Pass\",\"Fail\")", "IF(D2>=70,\"Pass\",\"Fail\")"]', 
 'IF function tests a condition and returns different values based on whether the condition is true or false.', 
 '["Use IF function for conditional logic", "Test if D2 is greater than or equal to 70", "Return \"Pass\" for true, \"Fail\" for false"]',
 'if,conditional,logic'),

('Text Functions', 'intermediate', 
 'Extract the first 5 characters from text in cell E1.', 
 'formula', '=LEFT(E1,5)', 
 '["=MID(E1,1,5)", "LEFT(E1,5)"]', 
 'LEFT function extracts a specified number of characters from the beginning of a text string.', 
 '["Think about extracting from the left side", "Use LEFT function with text and number of characters", "LEFT(E1,5) gets first 5 characters"]',
 'left,text,extraction'),

-- Advanced Questions  
('Data Analysis', 'advanced', 
 'Explain how you would use pivot tables to analyze sales performance by region and month. What are the key steps?', 
 'explanation', 
 'Select data range, insert pivot table, add Region to Rows area, Month to Columns area, Sales amount to Values area. Apply filters for specific periods and sort by totals for insights.', 
 '[]', 
 'Pivot tables summarize large datasets by grouping and aggregating data across multiple dimensions for analysis.', 
 '["Think about the main steps: select data, insert pivot table, configure fields", "Consider what goes in Rows, Columns, and Values areas", "Think about additional features like filters and sorting"]',
 'pivot,analysis,advanced'),

('Array Formulas', 'advanced', 
 'Create a formula to find the maximum value in column A where the corresponding value in column B equals "Active".', 
 'formula', '=MAX(IF(B:B="Active",A:A))', 
 '["=MAXIFS(A:A,B:B,\"Active\")", "{=MAX(IF(B:B=\"Active\",A:A))}"]', 
 'This uses an array formula with IF to conditionally find the maximum value based on criteria.', 
 '["Think about conditional maximum", "Use IF with MAX function", "Consider MAXIFS as modern alternative"]',
 'array,conditional,advanced'),

('Complex Scenarios', 'advanced', 
 'Describe how you would build a dynamic dashboard that automatically updates charts and KPIs when source data changes. Include the key Excel features you would use.', 
 'explanation', 
 'Use Excel Tables for dynamic ranges, PivotTables connected to tables for automatic refresh, named ranges with OFFSET/COUNTA for expanding data, conditional formatting for KPI indicators, and data validation for interactive filters.', 
 '[]', 
 'Dynamic dashboards require structured data sources and self-updating components that respond to data changes.', 
 '["Think about making data ranges expand automatically", "Consider how charts can update with new data", "Think about interactive elements for users"]',
 'dashboard,dynamic,advanced');

-- Create indexes for better performance
CREATE INDEX idx_questions_difficulty ON questions(difficulty);
CREATE INDEX idx_questions_category ON questions(category);
CREATE INDEX idx_questions_type ON questions(question_type);
CREATE INDEX idx_sessions_status ON interview_sessions(status);
CREATE INDEX idx_answers_session ON answers(session_id);
CREATE INDEX idx_answers_score ON answers(score);

-- Create views for common queries
CREATE VIEW session_summary AS
SELECT 
    s.id,
    s.role_level,
    s.started_at,
    s.completed_at,
    s.overall_score,
    COUNT(a.id) as questions_answered,
    AVG(a.score) as average_score,
    SUM(a.time_spent) as total_time
FROM interview_sessions s
LEFT JOIN answers a ON s.id = a.session_id
GROUP BY s.id, s.role_level, s.started_at, s.completed_at, s.overall_score;

CREATE VIEW question_analytics AS
SELECT 
    q.id,
    q.category,
    q.difficulty,
    q.question_type,
    COUNT(a.id) as times_asked,
    AVG(a.score) as average_score,
    AVG(a.time_spent) as average_time,
    COUNT(CASE WHEN a.score >= 80 THEN 1 END) as high_scores
FROM questions q
LEFT JOIN answers a ON q.id = a.question_id
GROUP BY q.id, q.category, q.difficulty, q.question_type;
