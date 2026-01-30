from flask import Flask, render_template, request, redirect, url_for
app = Flask(__name__)
todos = []

@app.route('/')
def home():
    return render_template('home.html', todos=todos)

@app.route('/add', methods=['POST'])
def add():
    # Get the todo item and day from the POST request
    todo_text = request.form.get('new-todo')
    day = request.form.get('day', 'Monday')
    
    if todo_text:
        # Store both text and day
        todos.append({'text': todo_text, 'day': day})
        
    return redirect(url_for('home'))

@app.route('/delete/<int:index>')
def delete(index):
    # Delete todo at the given index
    if 0 <= index < len(todos):
        todos.pop(index)
    return redirect(url_for('home'))

@app.route('/edit/<int:index>', methods=['GET', 'POST'])
def edit(index):
    if 0 <= index < len(todos):
        if request.method == 'POST':
            todo_text = request.form.get('new-todo')
            day = request.form.get('day')
            # Update todo
            todos[index] = {'text': todo_text, 'day': day}
            return redirect(url_for('home'))
        
        # GET: Show edit form
        todo = todos[index]
        return render_template('edit.html', todo=todo, index=index)
    
    return redirect(url_for('home'))

if __name__ == '__main__':
    print("Flask Todo App running at http://127.0.0.1:5000")
    app.run(debug=True)
