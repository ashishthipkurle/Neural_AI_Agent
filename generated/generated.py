from flask import Flask, render_template, request, redirect
app = Flask(__name__)
todo_list = []

@app.route('/')
def index():
    return render_template('index.html', todos=todo_list)

@app.route('/add', methods=['POST'])
def add():
    # Get the task from the POST request
    task = request.form.get('task')
    
    if task:
        todo_list.append(task)  # Add it to our list
        
    return redirect('/')  # Redirect back to the home page

if __name__ == '__main__':
    app.run()