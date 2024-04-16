#!/usr/bin/env python3
if __name__ == "__main__":
    print("STARTING UP, WAITING FOR INPUT")
    while True:
        user_input = input("Enter 'q' to quit: ")
        if user_input.lower() == 'q':
            break
        print("YOU INPUT:", user_input)