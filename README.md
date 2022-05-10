# Prodsim

materialt 
router 
controller 
ressource
Prozess

In einem Baum sind Prozesse und Materialien verbunden. 

Die Ressource als data class hat Prozesse , über ein list Attribute. 
Der Prozess hat eine bestimmte ID.  Je nach Zustand, also State, bieten Ressourcen unterschiedliche Prozesse an. 
Der Router gibt alle Optionen für Prozessel an, bietet also nachdem ein Material seinen Zustand geändert hat, alle targets an. Dies sind mögliche Ressourcen die einen Prozess durchführen.
Der Controller wählt eine oder mehrere der Optionen des Routers aus durch eine Request Funktion. Dadurch wird die Durchführung eines Prozesses angestoßen, der den Zustand eines materials oder einer Ressource ändert. 
Durch eine Logger class werden alle Zustandsänderungen gelogged, dies bezieht sich auf Ressourcen bei durchgeführte Prozesse, Materialien bei Zustandsänderungen durch Prozesse und Zustandsänderungen von Maschinen.
Fur manche Prozesse sind bestimmte Bedingungen vorhanden, wie das beispielsweise mehrere Einheiten Transportiert werden. Die Durchführung der Prozesse (eine Liste von Prozessen) läuft dabei auch je nach zustand der Ressource  unter verschiedenen Bedingungen ab. Die Prozessklasse hat aber diese Eigenschaft, da sie als Informationsklasse nur mit der Maschine verbunden ist, die nur Zustände uber sich selbst verwaltet.