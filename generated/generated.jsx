import React from 'react';

class TodoApp extends React.Component {
  constructor(props) {
    super(props);
    
    // Initialize state with an empty todo list
    this.state = { todos: [] };
  }
  
  handleAddTodo = (event) => {
    event.preventDefault();
        
    // Get the value of the input field
    const text = event.target[0].value;
    
    if(text) {
      // Add a new todo to the list
      this.setState((prevState) => ({ 
        todos: [...prevState.todos, { id: prevState.todos.length + 1, text }] 
      }));
        
      // Clear the input field
      event.target[0].value = '';
    }
  };
  
  handleDeleteTodo = (id) => {
    this.setState((prevState) => ({ 
      todos: prevState.todos.filter(todo => todo.id !== id) 
    }));
  };

  // Function to update a todo item
  handleUpdateTodo = (id, newText) => {
    this.setState((prevState) => ({
      todos: prevState.todos.map(todo => 
        todo.id === id ? { ...todo, text: newText } : todo
      )
    }));
  };
  
  render() {
    return (
      <div>
        <form onSubmit={this.handleAddTodo}>
          <input type="text" placeholder="New task..." />
          {/* Changed the color of 'Add' button to blue */}
          <button type="submit" style={{backgroundColor: "blue", color: "white"}}>Add</button>
        </form>
        
        {/* Display the list of todos */}
        <ul>
          {this.state.todos.map(todo => 
            <li key={todo.id}>
              {todo.text} 
              <button onClick={() => this.handleDeleteTodo(todo.id)} style={{backgroundColor: "blue", color: "white"}}>Delete</button>
              
              {/* Changed the color of 'Edit' button to blue */}
              <button onClick={() => this.handleUpdateTodo(todo.id, prompt("Enter new task")) } style={{backgroundColor: "blue", color: "white"}}>Edit</button>
            </li>
          )}
        </ul>
      </div>
    );
  }
}