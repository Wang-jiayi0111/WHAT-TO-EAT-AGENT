# Workflow Orchestration with AgentState

class AgentState:
    def __init__(self):
        """
        Initialize the AgentState with default values.
        """
        self.messages = []  # Stores the conversation history
        self.task_stack = []  # Stack of tasks to execute
        self.current_intent = None  # Current user intent
        self.active_user_id = None  # Active user ID
        self.active_constraints = {}  # Active constraints (e.g., allergies, preferences)
        self.logistics_buffer = {
            "recipe_requirements": {},  # Normalized recipe requirements
            "inventory_snapshot": {},  # Current inventory snapshot
            "shopping_list": {},  # Generated shopping list
        }
        self.expert_payloads = {}  # Intermediate results from expert nodes

    def update_intent(self, intent):
        """
        Update the current intent.

        :param intent: The new intent to set.
        """
        self.current_intent = intent

    def push_task(self, task):
        """
        Push a new task onto the task stack.

        :param task: The task to add.
        """
        self.task_stack.append(task)

    def pop_task(self):
        """
        Pop the top task from the task stack.

        :return: The popped task.
        """
        if self.task_stack:
            return self.task_stack.pop()
        return None

    def add_message(self, message):
        """
        Add a message to the conversation history.

        :param message: The message to add.
        """
        self.messages.append(message)

    def update_logistics_buffer(self, key, value):
        """
        Update a specific key in the logistics buffer.

        :param key: The key to update.
        :param value: The value to set.
        """
        if key in self.logistics_buffer:
            self.logistics_buffer[key] = value
        else:
            raise KeyError(f"Invalid logistics buffer key: {key}")