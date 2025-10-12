# Chat Workspace State Management - Quick Start Guide

## Overview

The improved chat workspace uses a reducer-based state management pattern with dedicated hooks for specific concerns.

## Basic Usage

```typescript
import { useChatWorkspaceState } from "./useChatWorkspaceState";
import { useSessionRestoration, useSessionPersistence } from "./useSessionRestoration";
import { useChatExecution } from "./useChatExecution";

function ChatWorkspace() {
  // 1. Initialize state management
  const { state, dispatch, actions, computed } = useChatWorkspaceState();
  
  // 2. Setup client reference
  const clientRef = useRef<ChatWorkflowClient>(myClient);
  
  // 3. Enable session restoration
  useSessionRestoration(
    clientRef,
    dispatch,
    state.restorationAttempts,
    computed.canRetryRestoration
  );
  
  // 4. Persist session to localStorage
  useSessionPersistence(state.sessionId);
  
  // 5. Setup chat execution
  const { executeChat, abortCurrentRequest } = useChatExecution(
    clientRef,
    dispatch,
    state.conversation,
    state.sessionId,
    modeId,
    state.defaultFilters,
    state.frequentlyOpenedPanels,
    buildFallbackSuggestions
  );
  
  // 6. Use state and actions
  return (
    <div>
      {state.conversation.map(entry => (
        <Message key={entry.id} entry={entry} />
      ))}
    </div>
  );
}
```

## State Access

### Reading State

```typescript
const { state, computed } = useChatWorkspaceState();

// Conversation
state.conversation           // Array of messages
state.feedbackSelections     // Record of feedback reactions
state.pendingFeedbackIds     // Set of pending feedback IDs

// Session
state.sessionId              // Current session ID
state.isRestoring            // Is restoration in progress?
state.restorationStatus      // 'idle' | 'loading' | 'success' | 'error' | 'retrying'
state.restorationError       // Error message if restoration failed
state.restorationAttempts    // Number of retry attempts

// Preferences
state.frequentlyOpenedPanels // Array of panel IDs
state.defaultFilters         // Search filters

// Streaming
state.isStreaming            // Is a message being generated?
state.activeAssistantId      // ID of message being streamed

// Errors
state.guardrail              // Guardrail violation details
state.errorMessage           // General error message
state.lastQuestion           // Last user question

// Computed
computed.hasTranscript       // Are there messages?
computed.canRetryRestoration // Can restoration be retried?
```

### Dispatching Actions

```typescript
const { dispatch, actions } = useChatWorkspaceState();

// Use dispatch for complex actions
dispatch({ 
  type: "START_STREAMING", 
  payload: { userEntry, assistantEntry, question } 
});

// Use helper actions for common operations
actions.updateAssistantFragment(assistantId, "Hello ");
actions.updateAssistantComplete(assistantId, "Hello world", citations);
actions.removeEntry(entryId);
actions.setGuardrail(guardrailState);
actions.clearGuardrail();
actions.setError("Something went wrong");
actions.setFeedbackPending(entryId, true);
actions.setFeedbackSelection(entryId, "like");
```

## Common Patterns

### Starting a Chat

```typescript
const { executeChat } = useChatExecution(/* ... */);

async function handleSubmit(question: string) {
  await executeChat(question);
}
```

### Handling Guardrails

```typescript
if (state.guardrail) {
  return (
    <ErrorCallout
      message={state.guardrail.message}
      traceId={state.guardrail.traceId}
    />
  );
}
```

### Showing Streaming State

```typescript
const transcript = state.conversation.map((entry) => {
  if (entry.role === "assistant") {
    const isActive = entry.id === state.activeAssistantId && state.isStreaming;
    return {
      ...entry,
      isStreaming: isActive,
      displayContent: entry.content || (isActive ? "Generating..." : "")
    };
  }
  return entry;
});
```

### Submitting Feedback

```typescript
async function handleFeedback(entryId: string, reaction: Reaction) {
  actions.setFeedbackPending(entryId, true);
  
  try {
    await submitFeedback({ /* ... */ });
    actions.setFeedbackSelection(entryId, reaction);
  } finally {
    actions.setFeedbackPending(entryId, false);
  }
}
```

### Resetting Session

```typescript
function handleReset() {
  abortCurrentRequest();
  dispatch({ type: "RESET_SESSION" });
  localStorage.removeItem("theo.chat.lastSessionId");
}
```

### Forking Session

```typescript
function handleFork() {
  dispatch({ type: "FORK_SESSION" });
  localStorage.removeItem("theo.chat.lastSessionId");
}
```

## Action Reference

### Session Restoration

```typescript
dispatch({ type: "START_RESTORATION" });

dispatch({ 
  type: "RESTORATION_SUCCESS", 
  payload: { sessionId, conversation, frequentlyOpenedPanels, defaultFilters, lastQuestion }
});

dispatch({ type: "RESTORATION_ERROR", error: "Error message" });
dispatch({ type: "RESTORATION_RETRY" });
dispatch({ type: "RESTORATION_COMPLETE" });
```

### Streaming

```typescript
dispatch({
  type: "START_STREAMING",
  payload: { userEntry, assistantEntry, question }
});

dispatch({
  type: "UPDATE_ASSISTANT_FRAGMENT",
  assistantId,
  content: "fragment text"
});

dispatch({
  type: "UPDATE_ASSISTANT_COMPLETE",
  assistantId,
  payload: { content: "full text", citations }
});

dispatch({ type: "STREAMING_COMPLETE", sessionId });
```

### Entry Management

```typescript
dispatch({ type: "REMOVE_ENTRY", entryId });
```

### Guardrails and Errors

```typescript
dispatch({ 
  type: "SET_GUARDRAIL", 
  guardrail: { message, traceId, suggestions, metadata }
});

dispatch({ type: "CLEAR_GUARDRAIL" });
dispatch({ type: "SET_ERROR", error: "Error message" });
```

### Feedback

```typescript
dispatch({ type: "SET_FEEDBACK_PENDING", entryId, pending: true });
dispatch({ type: "SET_FEEDBACK_SELECTION", entryId, reaction: "like" });
```

### Session Management

```typescript
dispatch({ type: "SET_SESSION_ID", sessionId: "new-id" });
dispatch({ 
  type: "SET_PREFERENCES", 
  payload: { frequentlyOpenedPanels, defaultFilters }
});
dispatch({ type: "RESET_SESSION" });
dispatch({ type: "FORK_SESSION" });
```

## Error Handling

### Session Restoration Errors

```typescript
if (state.restorationStatus === "error") {
  console.error("Restoration failed:", state.restorationError);
  
  if (computed.canRetryRestoration) {
    // Will automatically retry
    console.log(`Retry attempt ${state.restorationAttempts + 1}`);
  } else {
    // Max retries exceeded
    console.log("Session cleared");
  }
}
```

### Chat Execution Errors

```typescript
// Guardrail violations
if (state.guardrail) {
  // Show guardrail UI with suggestions
}

// General errors
if (state.errorMessage) {
  // Show error message
}
```

## Testing

### Testing the Reducer

```typescript
import { chatWorkspaceReducer } from "./useChatWorkspaceState";

test("START_STREAMING adds messages", () => {
  const initialState = { /* ... */ };
  const action = {
    type: "START_STREAMING",
    payload: { userEntry, assistantEntry, question }
  };
  
  const newState = chatWorkspaceReducer(initialState, action);
  
  expect(newState.conversation).toHaveLength(2);
  expect(newState.isStreaming).toBe(true);
  expect(newState.activeAssistantId).toBe(assistantEntry.id);
});
```

### Testing Hooks

```typescript
import { renderHook } from "@testing-library/react";
import { useChatWorkspaceState } from "./useChatWorkspaceState";

test("useChatWorkspaceState initializes correctly", () => {
  const { result } = renderHook(() => useChatWorkspaceState());
  
  expect(result.current.state.conversation).toEqual([]);
  expect(result.current.state.isStreaming).toBe(false);
  expect(result.current.computed.hasTranscript).toBe(false);
});
```

## Performance Tips

### 1. Memoize Callbacks

```typescript
const handleSubmit = useCallback(
  async (question: string) => {
    await executeChat(question);
  },
  [executeChat]
);
```

### 2. Memoize Derived Values

```typescript
const transcript = useMemo(
  () => state.conversation.map(formatEntry),
  [state.conversation, state.activeAssistantId, state.isStreaming]
);
```

### 3. Use React.memo for Message Components

```typescript
const Message = React.memo(({ entry }: { entry: ConversationEntry }) => {
  // ...
});
```

### 4. Clean Up Resources

```typescript
useEffect(() => {
  return () => {
    abortCurrentRequest();
  };
}, [abortCurrentRequest]);
```

## Debugging

### Log State Changes

```typescript
useEffect(() => {
  if (process.env.NODE_ENV === "development") {
    console.log("[ChatWorkspace] State:", state);
  }
}, [state]);
```

### Log Actions

```typescript
function debugReducer(state, action) {
  console.log("[Action]", action.type, action);
  const newState = chatWorkspaceReducer(state, action);
  console.log("[New State]", newState);
  return newState;
}
```

### Track Restoration

```typescript
useEffect(() => {
  console.log("Restoration status:", state.restorationStatus);
  if (state.restorationError) {
    console.error("Restoration error:", state.restorationError);
  }
}, [state.restorationStatus, state.restorationError]);
```

## Troubleshooting

### Session Not Restoring

1. Check localStorage for saved session ID
2. Verify API endpoint is accessible
3. Check console for restoration errors
4. Verify session data format

### Streaming Not Working

1. Check `state.isStreaming` is true
2. Verify `state.activeAssistantId` matches message ID
3. Check network tab for streaming response
4. Verify event handler is called

### State Not Updating

1. Ensure actions are dispatched
2. Check reducer for correct action type
3. Verify action payload structure
4. Use React DevTools to inspect state

## Best Practices

1. **Always use dispatch for state changes** - Never mutate state directly
2. **Use helper actions when available** - They're type-safe and convenient
3. **Clean up resources** - Always abort requests on unmount
4. **Handle errors gracefully** - Show user-friendly messages
5. **Test state transitions** - Reducer is easy to test
6. **Memoize expensive computations** - Use useMemo and useCallback
7. **Keep actions focused** - One action should do one thing well
8. **Document custom actions** - Add comments for complex logic
