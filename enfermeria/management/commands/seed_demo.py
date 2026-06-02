"""
Comando: python manage.py seed_demo
Crea 500 estudiantes, 2 consultas por estudiante, y 30 docentes.
"""
import random
import datetime
from django.core.management.base import BaseCommand
from django.utils import timezone
from enfermeria.models import Estudiante, Consulta, Docente

NOMBRES_M = ["Andrés","Carlos","Juan","Luis","Miguel","Diego","Sebastián","Felipe","Santiago","Alejandro",
             "Daniel","Camilo","Esteban","Mateo","Gabriel","Nicolás","David","Julián","Ricardo","Sergio",
             "Emmanuel","Christian","Álvaro","Hernando","Iván","Rodrigo","Tomás","Fabián","Mauricio","Gonzalo"]
NOMBRES_F = ["María","Laura","Ana","Valentina","Daniela","Isabela","Camila","Sofía","Mariana","Alejandra",
             "Juliana","Natalia","Paola","Andrea","Luisa","Paula","Claudia","Fernanda","Diana","Tatiana",
             "Lorena","Mónica","Angela","Yessica","Catalina","Marcela","Adriana","Sandra","Viviana","Lina"]
APELLIDOS = ["García","Rodríguez","Martínez","López","González","Hernández","Pérez","Sánchez","Ramírez","Torres",
             "Flores","Rivera","Gómez","Díaz","Cruz","Reyes","Morales","Jiménez","Vásquez","Álvarez",
             "Rojas","Castillo","Ortiz","Mendoza","Medina","Castro","Vargas","Ramos","Parra","Mora"]
GRADOS = [c[0] for c in Estudiante.GRADO_CHOICES]
SEXOS  = ['M','F','O']
SANGRES= [c[0] for c in Estudiante.TIPO_SANGRE_CHOICES]
MOTIVOS= [c[0] for c in Consulta.MOTIVO_CHOICES]
ESTADOS= [c[0] for c in Consulta.ESTADO_CHOICES]
AREAS  = [c[0] for c in Docente.AREA_CHOICES]
VINCUL = [c[0] for c in Docente.VINCULACION_CHOICES]
REGS   = [c[0] for c in Estudiante.REGIMEN_CHOICES]

class Command(BaseCommand):
    help = 'Inserta datos de demostración: 500 estudiantes, 2 consultas c/u, 30 docentes'

    def handle(self, *args, **kwargs):
        self.stdout.write('Creando 30 docentes...')
        docs_creados = 0
        for i in range(35):
            sexo = random.choice(['M','F'])
            nombre = f"{random.choice(NOMBRES_M if sexo=='M' else NOMBRES_F)} {random.choice(APELLIDOS)} {random.choice(APELLIDOS)}"
            cedula = str(random.randint(10000000,99999999))
            if Docente.objects.filter(cedula=cedula).exists():
                continue
            if docs_creados >= 30:
                break
            nac = datetime.date(random.randint(1970,1990), random.randint(1,12), random.randint(1,28))
            Docente.objects.create(
                nombre=nombre, cedula=cedula, fecha_nacimiento=nac, sexo=sexo,
                area=random.choice(AREAS), vinculacion=random.choice(VINCUL),
                telefono=f"3{random.randint(100000000,199999999)}",
                eps=random.choice(['Sura','Sanitas','Nueva EPS','Compensar','Famisanar']),
                regimen=random.choice(REGS), activo=random.random() > 0.1,
            )
            docs_creados += 1
        self.stdout.write(f'  -> {docs_creados} docentes creados')

        self.stdout.write('Creando 500 estudiantes con 2 consultas c/u...')
        est_creados = 0
        intentos = 0
        while est_creados < 500 and intentos < 600:
            intentos += 1
            sexo = random.choice(['M','F'])
            nombre = f"{random.choice(NOMBRES_M if sexo=='M' else NOMBRES_F)} {random.choice(APELLIDOS)} {random.choice(APELLIDOS)}"
            doc = str(random.randint(1000000000,1099999999))
            if Estudiante.objects.filter(numero_documento=doc).exists():
                continue
            nac = datetime.date(random.randint(2006,2016), random.randint(1,12), random.randint(1,28))
            est = Estudiante.objects.create(
                nombre=nombre, numero_documento=doc, grado=random.choice(GRADOS),
                fecha_nacimiento=nac, sexo=sexo,
                tipo_sangre=random.choice(SANGRES),
                acudiente=f"{random.choice(APELLIDOS)} {random.choice(APELLIDOS)}",
                telefono_acudiente=f"3{random.randint(100000000,199999999)}",
                eps=random.choice(['Sura','Sanitas','Nueva EPS','Compensar','Famisanar','']),
                regimen=random.choice(REGS),
                alergias=random.choice(['','Polen','Polvo','Penicilina','Mariscos','']),
            )
            for _ in range(2):
                dias = random.randint(1, 180)
                dt = timezone.now() - datetime.timedelta(days=dias, hours=random.randint(0,8))
                Consulta.objects.create(
                    estudiante=est,
                    fecha_hora=dt,
                    hora_atencion=dt.time(),
                    motivo=random.choice(MOTIVOS),
                    descripcion_sintomas=random.choice([
                        'Paciente refiere malestar general.',
                        'Presenta fiebre desde ayer.',
                        'Golpe durante educacion fisica.',
                        'Dolor abdominal leve.',
                        'Mareo y nauseas.',
                    ]),
                    tratamiento=random.choice([
                        'Reposo y observacion.',
                        'Hidratacion oral.',
                        'Aplicacion de hielo.',
                        'Llamada al acudiente.',
                    ]),
                    estado=random.choice(ESTADOS),
                )
            est_creados += 1
        self.stdout.write(f'  -> {est_creados} estudiantes y {est_creados*2} consultas creados')
        self.stdout.write(self.style.SUCCESS('Datos de demostracion insertados correctamente!'))
