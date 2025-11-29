> >>def cmd_code(self, action, *args):
> > >if action == "read":
> > >if >not args:
> > >return "Нужно указать файл: /code read main.py"
> > file_name = args[0]
> > >with open(file_name, 'r') >as file:
> > >return file.read()
> > >elif action == "execute":
> > # Логика выполнения кода >pass >else:
> > >return f"Неизвестная команда: {action}"