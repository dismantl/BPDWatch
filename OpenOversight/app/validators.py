from us import states


def state_validator(state):
    list_of_states = [st.abbr for st in states.STATES]

    if state not in list_of_states and state != 'DC':
        raise ValueError('Not a valid US state')

    return state
