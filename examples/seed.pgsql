begin; 

insert into author(id, name) values
    (1, 'hep tupman'), 
    (2, 'pup tipson')
on conflict (id) do nothing; 

insert into book(author_id, name, catalog) values 
    (1, 'Gone with the Fin', 'Boring'), 
    (2, 'Paws', 'Cute'), 
    (1, 'Snore of the Worlds', 'Lame'), 
    (2, 'Dringus', 'Dumb')
on conflict (id) do nothing; 

end;